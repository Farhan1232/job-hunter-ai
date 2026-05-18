"""CV-vs-job matching with multi-provider fallback.

Order:
  1. Gemini (free tier ~20 req/day on gemini-flash-latest)
  2. Groq (free tier ~6000 req/day on Llama 3.3 70B) — kicks in when Gemini quota dies

Same MatchResult shape from both. Keyword pre-filter runs first to avoid
wasting API calls on obviously irrelevant jobs.
"""
import os
import json
import re
import asyncio
from dataclasses import dataclass

import httpx
import google.generativeai as genai

from .sources.base import Job


@dataclass
class MatchResult:
    score: int
    reason: str
    missing: list[str]


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GROQ_MODEL   = os.getenv("GROQ_MODEL",   "llama-3.3-70b-versatile")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"


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


def _build_prompt(cv_text: str, job: Job) -> str:
    return f"""You are a recruiter. Compare CV to job. Return JSON only.

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


# ---------- Provider: Gemini ----------

def _gemini_configured() -> bool:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return False
    genai.configure(api_key=key)
    return True


async def _score_gemini(model, cv_text: str, job: Job) -> tuple[MatchResult, bool]:
    """Returns (result, is_quota_error)."""
    try:
        resp = await asyncio.to_thread(model.generate_content, _build_prompt(cv_text, job))
        return _parse_response(resp.text or ""), False
    except Exception as e:
        msg = str(e)
        is_quota = "429" in msg or "quota" in msg.lower() or "rate" in msg.lower()
        print(f"[gemini] {job.id}: {msg[:120]}")
        return MatchResult(score=0, reason=f"err: gemini {msg[:80]}", missing=[]), is_quota


# ---------- Provider: Groq ----------

async def _score_groq(client: httpx.AsyncClient, cv_text: str, job: Job) -> tuple[MatchResult, bool]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return MatchResult(score=0, reason="err: no GROQ_API_KEY", missing=[]), False
    try:
        r = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": _build_prompt(cv_text, job)}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=45,
        )
        if r.status_code == 429:
            print(f"[groq] {job.id}: 429 rate-limited")
            return MatchResult(score=0, reason="err: groq 429", missing=[]), True
        if r.status_code >= 400:
            print(f"[groq] {job.id}: {r.status_code} {r.text[:160]}")
            return MatchResult(score=0, reason=f"err: groq {r.status_code}", missing=[]), False
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_response(text), False
    except Exception as e:
        print(f"[groq] {job.id}: {type(e).__name__}: {e}")
        return MatchResult(score=0, reason=f"err: groq {e}", missing=[]), False


# ---------- Orchestrator ----------

async def score_jobs(jobs: list[Job], cv_text: str, max_jobs: int = 20) -> list[tuple[Job, MatchResult]]:
    """Score sequentially. Use Gemini first; on persistent 429 switch to Groq."""
    if not jobs:
        return []
    jobs = jobs[:max_jobs]

    gemini_ok = _gemini_configured()
    groq_ok = bool(os.getenv("GROQ_API_KEY"))
    if not gemini_ok and not groq_ok:
        raise RuntimeError("Need at least one of GEMINI_API_KEY or GROQ_API_KEY")

    gemini_model = genai.GenerativeModel(GEMINI_MODEL) if gemini_ok else None
    gemini_dead = not gemini_ok
    consec_gemini_429 = 0

    out: list[tuple[Job, MatchResult]] = []
    async with httpx.AsyncClient() as http:
        for i, j in enumerate(jobs):
            res: MatchResult
            used = ""

            if not gemini_dead and gemini_model is not None:
                res, is_quota = await _score_gemini(gemini_model, cv_text, j)
                used = "gemini"
                if is_quota:
                    consec_gemini_429 += 1
                    if consec_gemini_429 >= 3:
                        print("[matcher] Gemini exhausted — switching to Groq")
                        gemini_dead = True
                else:
                    consec_gemini_429 = 0

            if (gemini_dead or res.score == 0 and res.reason.startswith("err: gemini")) and groq_ok:
                res, _ = await _score_groq(http, cv_text, j)
                used = "groq"

            if used and res.score > 0:
                res.reason = f"[{used}] {res.reason}" if not res.reason.startswith("[") else res.reason
            out.append((j, res))

            if i < len(jobs) - 1:
                # Gemini ~10 RPM (7s), Groq ~30 RPM (2s). Use the slower one to be safe.
                await asyncio.sleep(2 if gemini_dead else 7)
    return out
