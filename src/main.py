"""Job hunter — runs once, fetches jobs from all free sources,
scores them against your CV with Gemini, and sends Telegram alerts.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

from .config import Config
from .cv_parser import load_cv_text
from .storage import Storage
from . import matcher
from . import notifier
from .sources import (
    remotive, remoteok, arbeitnow, himalayas,
    adzuna, jooble, rss_feeds,
)


def dedupe_by_id(jobs):
    seen = {}
    for j in jobs:
        if j.id not in seen:
            seen[j.id] = j
    return list(seen.values())


async def fetch_all(cfg: Config):
    print("→ fetching jobs from all sources...")
    coros = [
        remotive.fetch(cfg.keywords),
        remoteok.fetch(cfg.keywords),
        arbeitnow.fetch(cfg.keywords),
        himalayas.fetch(cfg.keywords),
        adzuna.fetch(cfg.keywords, cfg.adzuna_countries),
        jooble.fetch(cfg.keywords, cfg.jooble_locations),
        rss_feeds.fetch(cfg.keywords),
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)
    all_jobs = []
    for r in results:
        if isinstance(r, Exception):
            print(f"  source failed: {r}")
            continue
        all_jobs.extend(r)
    print(f"→ fetched {len(all_jobs)} raw postings")
    deduped = dedupe_by_id(all_jobs)
    print(f"→ {len(deduped)} after dedup")
    return deduped


async def run():
    load_dotenv()
    cfg = Config.load()

    cv_text = load_cv_text(cfg.cv_path)
    print(f"→ loaded CV ({len(cv_text)} chars)")

    storage = Storage()
    storage.prune_old(60)

    all_jobs = await fetch_all(cfg)
    new_jobs = storage.filter_unseen(all_jobs)
    print(f"→ {len(new_jobs)} new (unseen) jobs")

    if not new_jobs:
        print("→ nothing new")
        return

    pre = matcher.keyword_prefilter(new_jobs, cv_text, min_overlap=3)
    print(f"→ {len(pre)} after keyword pre-filter")

    if not pre:
        storage.mark_seen(new_jobs)
        return

    scored = await matcher.score_jobs(pre, cv_text, max_jobs=60)
    scored.sort(key=lambda t: t[1].score, reverse=True)

    above = [(j, m) for (j, m) in scored if m.score >= cfg.min_match_score]
    print(f"→ {len(above)} above {cfg.min_match_score}% threshold")

    to_send = above[: cfg.max_alerts_per_run]
    sent_ids: set[str] = set()
    sent = 0
    for job, match in to_send:
        if await notifier.send_job(job, match):
            sent += 1
            sent_ids.add(job.id)
        await asyncio.sleep(0.5)

    # Mark seen so we don't re-process next run:
    #   - jobs filtered out by keyword pre-filter (irrelevant)
    #   - jobs that got a real score below threshold
    #   - jobs we successfully alerted on
    # NOT mark seen (retry next run):
    #   - jobs above threshold whose alert failed
    #   - jobs that errored during scoring (e.g. Gemini quota)
    pre_ids = {j.id for j in pre}
    filtered_out = [j for j in new_jobs if j.id not in pre_ids]
    scored_real = [j for (j, m) in scored
                   if m.score < cfg.min_match_score
                   and not m.reason.startswith(("err", "skipped", "parse"))]
    alerted = [j for (j, _) in to_send if j.id in sent_ids]
    to_mark = filtered_out + scored_real + alerted
    storage.mark_seen(to_mark)
    print(f"→ sent {sent} alerts; marked {len(to_mark)} seen ({len(new_jobs) - len(to_mark)} will retry)")
    await notifier.send_summary(len(all_jobs), len(new_jobs), sent)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
