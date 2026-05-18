"""Notifications via Discord webhook (preferred — works in Pakistan)
or Telegram (works only where Telegram API is reachable, including GitHub Actions).

If DISCORD_WEBHOOK_URL is set, Discord is used.
Otherwise, Telegram is used if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set.
If neither, alerts are just printed to console.
"""
import os
import httpx
import html


TG_API = "https://api.telegram.org/bot{token}/sendMessage"


def _esc_html(text: str) -> str:
    return html.escape(text or "")


def _channel() -> str:
    if os.getenv("DISCORD_WEBHOOK_URL"):
        return "discord"
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        return "telegram"
    return "console"


def format_alert_telegram(job, match) -> str:
    score = match.score
    bar = "[GREAT]" if score >= 75 else "[GOOD]" if score >= 60 else "[OK]"
    lines = [
        f"{bar} <b>{score}% match</b> — {_esc_html(job.title)}",
        f"Company: {_esc_html(job.company)}",
        f"Location: {_esc_html(job.location)}" + (" (Remote)" if job.remote else ""),
        f"<a href=\"{_esc_html(job.url)}\">Apply here</a>",
        f"Source: {_esc_html(job.source)}",
    ]
    if job.salary:
        lines.append(f"Salary: {_esc_html(job.salary)}")
    if match.reason:
        lines.append(f"Why: {_esc_html(match.reason)}")
    if match.missing:
        lines.append("Missing: " + _esc_html(", ".join(match.missing)))
    return "\n".join(lines)


def format_alert_discord(job, match) -> dict:
    score = match.score
    color = 0x2ecc71 if score >= 75 else 0xf1c40f if score >= 60 else 0xe67e22
    fields = [
        {"name": "Company", "value": job.company or "—", "inline": True},
        {"name": "Location",
         "value": (job.location or "—") + (" (Remote)" if job.remote else ""),
         "inline": True},
        {"name": "Source", "value": job.source or "—", "inline": True},
    ]
    if job.salary:
        fields.append({"name": "Salary", "value": job.salary, "inline": True})
    if match.reason:
        fields.append({"name": "Why", "value": match.reason[:1024], "inline": False})
    if match.missing:
        fields.append({"name": "Missing skills",
                       "value": ", ".join(match.missing)[:1024], "inline": False})
    embed = {
        "title": f"{score}% — {(job.title or '')[:240]}",
        "url": job.url or None,
        "color": color,
        "fields": fields,
    }
    return {"embeds": [embed]}


async def _send_discord(text_or_payload) -> bool:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    payload = (text_or_payload
               if isinstance(text_or_payload, dict)
               else {"content": text_or_payload})
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=payload)
            if r.status_code not in (200, 204):
                print(f"[notifier] discord {r.status_code}: {r.text[:200]}")
                return False
            return True
        except Exception as e:
            print(f"[notifier] discord error: {type(e).__name__}: {e!r}")
            return False


async def _send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = TG_API.format(token=token)
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            if r.status_code != 200:
                print(f"[notifier] telegram {r.status_code}: {r.text[:200]}")
                return False
            return True
        except Exception as e:
            print(f"[notifier] telegram error: {type(e).__name__}: {e!r}")
            return False


async def send_job(job, match) -> bool:
    ch = _channel()
    if ch == "discord":
        return await _send_discord(format_alert_discord(job, match))
    if ch == "telegram":
        return await _send_telegram(format_alert_telegram(job, match))
    # console fallback
    print(f"[ALERT] {match.score}% — {job.title} @ {job.company} — {job.url}")
    return True


async def send_text(text: str) -> bool:
    ch = _channel()
    if ch == "discord":
        return await _send_discord(text)
    if ch == "telegram":
        return await _send_telegram(text)
    print(text)
    return True


# Back-compat aliases (used by older code)
async def send(text: str) -> bool:
    return await send_text(text)


def format_alert(job, match):
    # legacy helper — returns text for Telegram; Discord path uses send_job directly
    return format_alert_telegram(job, match)


async def send_summary(total_found: int, total_new: int, sent: int) -> None:
    await send_text(
        f"Job hunt finished\n"
        f"  Found: {total_found}\n"
        f"  New: {total_new}\n"
        f"  Alerts sent: {sent}"
    )
