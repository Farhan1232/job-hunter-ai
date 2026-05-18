import httpx
from .base import Job

API = "https://himalayas.app/jobs/api"


async def fetch(keywords: list[str]) -> list[Job]:
    jobs: list[Job] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for kw in keywords:
            try:
                r = await client.get(API, params={"title": kw})
                r.raise_for_status()
                data = r.json()
                items = data.get("jobs") if isinstance(data, dict) else data
                if not items:
                    continue
                for j in items:
                    jid = j.get("guid") or j.get("id") or j.get("applicationLink")
                    if not jid:
                        continue
                    jobs.append(Job(
                        id=f"himalayas-{jid}",
                        source="Himalayas",
                        title=j.get("title", ""),
                        company=j.get("companyName") or j.get("company", ""),
                        location=", ".join(j.get("locationRestrictions", []) or []) or "Worldwide",
                        url=j.get("applicationLink") or j.get("url", ""),
                        description=j.get("excerpt") or j.get("description", "") or "",
                        posted_date=str(j.get("pubDate", "")),
                        remote=True,
                        tags=j.get("categories", []) or [],
                    ))
            except Exception as e:
                print(f"[himalayas] {kw}: {e}")
    return jobs
