import httpx
from .base import Job

API = "https://remoteok.com/api"


async def fetch(keywords: list[str]) -> list[Job]:
    jobs: list[Job] = []
    headers = {"User-Agent": "job-hunter-ai/1.0"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        try:
            r = await client.get(API)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[remoteok] fetch error: {e}")
            return jobs

    kw_lower = [k.lower() for k in keywords]
    for j in data:
        if not isinstance(j, dict) or "id" not in j:
            continue
        title = j.get("position", "") or j.get("title", "")
        tags = [t.lower() for t in (j.get("tags", []) or [])]
        haystack = (title + " " + " ".join(tags)).lower()
        if not any(kw in haystack for kw in kw_lower):
            continue
        jobs.append(Job(
            id=f"remoteok-{j['id']}",
            source="RemoteOK",
            title=title,
            company=j.get("company", ""),
            location=j.get("location") or "Worldwide",
            url=j.get("url", "") or j.get("apply_url", ""),
            description=j.get("description", ""),
            posted_date=j.get("date"),
            salary=(f"${j['salary_min']}-${j['salary_max']}"
                    if j.get("salary_min") and j.get("salary_max") else None),
            remote=True,
            tags=j.get("tags", []) or [],
        ))
    return jobs
