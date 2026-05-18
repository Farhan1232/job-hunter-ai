import httpx
from .base import Job

API = "https://remotive.com/api/remote-jobs"


async def fetch(keywords: list[str]) -> list[Job]:
    jobs: list[Job] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for kw in keywords:
            try:
                r = await client.get(API, params={"search": kw})
                r.raise_for_status()
                for j in r.json().get("jobs", []):
                    jobs.append(Job(
                        id=f"remotive-{j['id']}",
                        source="Remotive",
                        title=j.get("title", ""),
                        company=j.get("company_name", ""),
                        location=j.get("candidate_required_location") or "Worldwide",
                        url=j.get("url", ""),
                        description=j.get("description", ""),
                        posted_date=j.get("publication_date"),
                        salary=j.get("salary") or None,
                        remote=True,
                        tags=j.get("tags", []) or [],
                    ))
            except Exception as e:
                print(f"[remotive] {kw}: {e}")
    return jobs
