# Job Hunter AI

Hunts jobs from many sources every hour, scores each one against your CV with Gemini, and sends Telegram alerts with the direct apply link.

**Cost: 0. Forever.**

## What it does

1. Every hour, fetches jobs from:
   - **Remotive, RemoteOK, Arbeitnow, Himalayas** — remote jobs worldwide
   - **Adzuna** — USA, UK, Germany, UAE, India, Singapore
   - **Jooble** — Pakistan, UAE, Qatar, Saudi, Oman, Kuwait, Bahrain, Germany, Netherlands, UK, USA
   - **Rozee.pk** — Pakistan
   - **Indeed RSS** — USA, UK, UAE, Qatar, Germany
2. Filters by your keywords (`cyber security`, `flutter developer`, etc.)
3. Deduplicates against jobs you've already been alerted about
4. Pre-filters using keyword overlap with your CV
5. Scores top candidates with **Gemini 1.5 Flash** (free tier) — gives a 0-100% match + reasoning + missing skills
6. Sends Telegram alert for every job above your threshold (default 50%)

## Setup — one-time, ~15 minutes

### 1. Get all the free API keys

| Service | Where | Cost |
|---|---|---|
| **Telegram bot token** | Open Telegram → message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts | Free |
| **Telegram chat ID** | Message [@userinfobot](https://t.me/userinfobot) | Free |
| **Gemini API key** | https://aistudio.google.com/apikey | Free |
| **Adzuna keys** | https://developer.adzuna.com → register | Free (250/day) |
| **Jooble key** | https://jooble.org/api/about → request | Free |

### 2. Put your CV at `data/cv.pdf`

```bash
cp /path/to/your_cv.pdf data/cv.pdf
```

You can have multiple — just point `cv_path` in `config.yaml` to whichever one you want this run to use.

### 3. Edit `config.yaml`

Adjust keywords, countries, score threshold to your taste.

### 4. Test it locally first

```bash
cd /home/farhan/Documents/job-hunter-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env with your keys
python -m src.main
```

You should get Telegram alerts within a minute.

### 5. Push to GitHub for free 24/7 hosting

```bash
git init
git add .
git commit -m "Initial commit"
# Create a private repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/job-hunter-ai.git
git push -u origin main
```

### 6. Add secrets to your GitHub repo

On GitHub: **Settings → Secrets and variables → Actions → New repository secret**

Add each of these (same names as in `.env`):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY`
- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`
- `JOOBLE_API_KEY`

### 7. Done

The workflow runs every hour automatically. To trigger it manually now: **Actions → Job Hunter → Run workflow**.

## Tuning

- **Too many alerts?** Raise `min_match_score` to 65 or 70 in `config.yaml`
- **Not enough alerts?** Lower threshold to 40, add more keywords, or add more Jooble locations
- **Want it more often?** Change cron in `.github/workflows/job-hunter.yml` (e.g. `*/30 * * * *` for every 30 min). Free tier gives 2000 mins/month — every-30-min uses ~720 mins/month, every hour ~360.
- **Different CV per niche?** Duplicate the workflow file, change `cv_path` per copy.

## Project layout

```
src/
  main.py           — entry point, orchestrates everything
  config.py         — loads config.yaml
  cv_parser.py      — reads your PDF CV
  matcher.py        — Gemini scoring + keyword pre-filter
  notifier.py       — sends Telegram alerts
  storage.py        — SQLite dedup (no re-alerts)
  sources/
    base.py         — Job dataclass
    remotive.py     — remote jobs API
    remoteok.py     — remote jobs API
    arbeitnow.py    — EU + remote API
    himalayas.py    — remote jobs API
    adzuna.py       — multi-country API
    jooble.py       — 70+ countries API
    rss_feeds.py    — Rozee.pk, Indeed RSS feeds
config.yaml         — your filters
.github/workflows/  — GitHub Actions cron
data/cv.pdf         — your CV (you provide)
data/seen_jobs.db   — SQLite dedup store (auto-created)
```

## Bonus: also get LinkedIn coverage for free

GitHub Actions can't easily scrape LinkedIn (they block bots). Easy free workaround: set up **Google Alerts** at https://www.google.com/alerts with queries like:

- `"cyber security" "Pakistan" site:linkedin.com/jobs`
- `"flutter developer" "remote" site:linkedin.com/jobs`
- `"SOC analyst" "UAE" site:linkedin.com/jobs`

Google emails you when new LinkedIn job pages match. Free, instant, official.
