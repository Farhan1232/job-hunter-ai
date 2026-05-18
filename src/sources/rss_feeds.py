"""Generic RSS-based sources: Rozee.pk, Bayt, Mustakbil, Indeed RSS."""
import asyncio
import hashlib
from urllib.parse import quote_plus
import feedparser
from .base import Job


def _slug(s: str) -> str:
    return quote_plus(s.lower().replace(" ", "-"))


def _make_feeds(keywords: list[str]) -> list[tuple[str, str, str, str]]:
    """Return list of (source_name, country/region, url, default_location)."""
    feeds: list[tuple[str, str, str, str]] = []
    for kw in keywords:
        # Rozee.pk — Pakistan
        feeds.append((
            "Rozee.pk", "Pakistan",
            f"https://www.rozee.pk/job/jsearch/q/{_slug(kw)}/fc/0/feed/rss",
            "Pakistan",
        ))
        # Indeed RSS — works in some regions still
        for tld, loc in [("com", "USA"), ("co.uk", "UK"), ("ae", "UAE"),
                         ("qa", "Qatar"), ("de", "Germany")]:
            feeds.append((
                f"Indeed-{loc}", loc,
                f"https://{tld}.indeed.com/rss?q={quote_plus(kw)}",
                loc,
            ))
    return feeds


def _parse_one(name: str, region: str, url: str, default_loc: str) -> list[Job]:
    out: list[Job] = []
    try:
        d = feedparser.parse(url)
        for entry in d.entries[:50]:
            link = entry.get("link", "")
            if not link:
                continue
            jid = hashlib.md5(link.encode()).hexdigest()[:16]
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            out.append(Job(
                id=f"{name.lower()}-{jid}",
                source=name,
                title=title,
                company=entry.get("author", "") or "",
                location=default_loc,
                url=link,
                description=summary,
                posted_date=entry.get("published", ""),
                remote="remote" in (title + summary).lower(),
            ))
    except Exception as e:
        print(f"[{name}] {url}: {e}")
    return out


async def fetch(keywords: list[str]) -> list[Job]:
    feeds = _make_feeds(keywords)
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, _parse_one, name, region, url, default_loc)
        for name, region, url, default_loc in feeds
    ])
    return [j for sub in results for j in sub]
