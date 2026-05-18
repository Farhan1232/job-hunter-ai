import os
import hashlib
import httpx
from .base import Job


async def fetch(keywords: list[str], locations: list[str]) -> list[Job]:
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        print("[jooble] no API key — skipping")
        return []

    jobs: list[Job] = []
    url = f"https://jooble.org/api/{key}"
    async with httpx.AsyncClient(timeout=30) as client:
        for loc in locations:
            for kw in keywords:
                try:
                    r = await client.post(url, json={
                        "keywords": kw,
                        "location": loc,
                    })
                    r.raise_for_status()
                    for j in r.json().get("jobs", []):
                        link = j.get("link", "")
                        jid = hashlib.md5(link.encode()).hexdigest()[:16] if link else None
                        if not jid:
                            continue
                        jobs.append(Job(
                            id=f"jooble-{jid}",
                            source=f"Jooble-{loc}",
                            title=j.get("title", ""),
                            company=j.get("company", ""),
                            location=j.get("location", loc),
                            url=link,
                            description=j.get("snippet", ""),
                            posted_date=j.get("updated"),
                            salary=j.get("salary") or None,
                            remote="remote" in (j.get("title", "") + j.get("snippet", "")).lower(),
                        ))
                except Exception as e:
                    print(f"[jooble] {loc}/{kw}: {e}")
    return jobs
