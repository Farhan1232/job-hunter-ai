import os
import httpx
from .base import Job


async def fetch(keywords: list[str], countries: list[str]) -> list[Job]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("[adzuna] no credentials — skipping")
        return []

    jobs: list[Job] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for country in countries:
            for kw in keywords:
                url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                try:
                    r = await client.get(url, params={
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": kw,
                        "results_per_page": 20,
                        "content-type": "application/json",
                    })
                    r.raise_for_status()
                    for j in r.json().get("results", []):
                        loc = j.get("location", {}).get("display_name", "")
                        jobs.append(Job(
                            id=f"adzuna-{j['id']}",
                            source=f"Adzuna-{country.upper()}",
                            title=j.get("title", ""),
                            company=j.get("company", {}).get("display_name", ""),
                            location=loc or country.upper(),
                            url=j.get("redirect_url", ""),
                            description=j.get("description", ""),
                            posted_date=j.get("created"),
                            salary=(f"{j.get('salary_min')}-{j.get('salary_max')}"
                                    if j.get("salary_min") else None),
                            remote="remote" in (j.get("title", "") + " " + j.get("description", "")).lower(),
                        ))
                except Exception as e:
                    print(f"[adzuna] {country}/{kw}: {e}")
    return jobs
