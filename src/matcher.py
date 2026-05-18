"""CV-vs-job matching using Gemini (free tier).

Two-stage:
  1. Cheap keyword pre-filter — only score jobs whose title/desc overlaps the CV.
  2. Gemini scoring — percent + 1-line reason + missing skills.
"""
import os
import json
import re
import asyncio
from dataclasses import dataclass

import google.generativeai as genai

from .sources.base import Job


@dataclass
class MatchResult:
    score: int            # 0-100
    reason: str
    missing: list[str]


_MODEL_NAME = "gemini-flash-latest"  # free tier, fast, always points to current flash


def _configure():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    genai.configure(api_key=key)


def _cv_keywords(cv_text: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", cv_text.lower())
    stop = {"the", "and", "for", "with", "from", "this", "that", "have", "has",
            "are", "was", "were", "you", "your", "our", "their", "but", "not",
            "all", "any", "can", "will", "would", "should", "into", "out", "of",
            "to", "in", "on", "at", "by", "is", "an", "a", "as", "or", "be"}
    return {w for w in words if w not in stop and len(w) >= 3}


def keyword_prefilter(jobs: list[Job], cv_text: str, min_overlap: int = 3) -> list[Job]:
    cv_kw = _cv_keywords(cv_text)
    out = []
    for j in jobs:
        text = (j.title + " " + j.short_desc(2000)).lower()
        job_words = set(re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", text))
        overlap = len(cv_kw & job_words)
        if overlap >= min_overlap:
            j.tags = j.tags + [f"_overlap={overlap}"]
            out.append(j)
    out.sort(key=lambda j: int([t for t in j.tags if t.startswith("_overlap=")][-1].split("=")[1]),
             reverse=True)
    return out


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_response(text: str) -> MatchResult:
    m = _JSON_RE.search(text)
    if not m:
        return MatchResult(score=0, reason="parse error", missing=[])
    try:
        data = json.loads(m.group(0))
        return MatchResult(
            score=int(data.get("score", 0)),
            reason=str(data.get("reason", ""))[:200],
            missing=[str(x)[:40] for x in (data.get("missing") or [])][:5],
        )
    except Exception:
        return MatchResult(score=0, reason="parse error", missing=[])


async def score_job(model, cv_text: str, job: Job) -> MatchResult:
    prompt = f"""You are a recruiter. Compare CV to job. Return JSON only.

CV:
{cv_text[:4000]}

JOB TITLE: {job.title}
COMPANY: {job.company}
LOCATION: {job.location}
DESCRIPTION:
{job.short_desc(2500)}

Return ONLY this JSON (no markdown, no prose):
{{"score": <0-100 int — how well CV matches>, "reason": "<one short sentence>", "missing": ["skill1","skill2"]}}
"""
    try:
        resp = await asyncio.to_thread(model.generate_content, prompt)
        return _parse_response(resp.text or "")
    except Exception as e:
        print(f"[matcher] {job.id}: {e}")
        return MatchResult(score=0, reason=f"err: {e}", missing=[])


async def score_jobs(jobs: list[Job], cv_text: str, max_jobs: int = 20) -> list[tuple[Job, MatchResult]]:
    """Score sequentially with a 7s gap — stays under Gemini free-tier 10 RPM.
    Short-circuits if we hit the daily quota (429) so we don't burn calls.
    """
    if not jobs:
        return []
    _configure()
    model = genai.GenerativeModel(_MODEL_NAME)
    jobs = jobs[:max_jobs]

    out = []
    quota_exhausted = False
    consec_429 = 0
    for i, j in enumerate(jobs):
        if quota_exhausted:
            out.append((j, MatchResult(score=0, reason="skipped: Gemini quota exhausted", missing=[])))
            continue
        res = await score_job(model, cv_text, j)
        out.append((j, res))
        if "429" in res.reason:
            consec_429 += 1
            if consec_429 >= 3:
                print("[matcher] hit 3 consecutive 429s — stopping to preserve quota")
                quota_exhausted = True
        else:
            consec_429 = 0
        if i < len(jobs) - 1 and not quota_exhausted:
            await asyncio.sleep(7)
    return out
