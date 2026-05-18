import httpx
from .base import Job

API = "https://www.arbeitnow.com/api/job-board-api"


async def fetch(keywords: list[str]) -> list[Job]:
    jobs: list[Job] = []
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(API)
            r.raise_for_status()
            data = r.json().get("data", [])
        except Exception as e:
            print(f"[arbeitnow] {e}")
            return jobs

    kw_lower = [k.lower() for k in keywords]
    for j in data:
        title = j.get("title", "")
        tags = [t.lower() for t in (j.get("tags", []) or [])]
        haystack = (title + " " + " ".join(tags) + " " + (j.get("description") or "")).lower()
        if not any(kw in haystack for kw in kw_lower):
            continue
        jobs.append(Job(
            id=f"arbeitnow-{j.get('slug', '')}",
            source="Arbeitnow",
            title=title,
            company=j.get("company_name", ""),
            location=j.get("location") or "Europe",
            url=j.get("url", ""),
            description=j.get("description", ""),
            posted_date=str(j.get("created_at", "")),
            remote=bool(j.get("remote")),
            tags=j.get("tags", []) or [],
        ))
    return jobs
