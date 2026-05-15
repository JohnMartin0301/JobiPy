"""
notifier/discord.py — Discord webhook notification sender.

Sends rich embed cards for each job. Handles overflow:
  1-5 jobs → full cards
  6+ jobs  → top 5 cards + overflow summary
"""

import logging
import requests
from config import DISCORD_WEBHOOK_URL, DISCORD_MAX_JOBS

logger = logging.getLogger(__name__)

_TIMEOUT = 10

# Freshness tier → embed colour (decimal)
_COLOUR = {
    "high":   0x57F287,  # green
    "normal": 0x5865F2,  # blurple
    "low":    0xFEE75C,  # yellow
}


def _format_posted(job: dict) -> str:
    days = job.get("posted_days")
    raw  = job.get("posted_date", "")
    if days is None:
        return raw or "Unknown"
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


def _build_embed(job: dict) -> dict:
    tier   = job.get("freshness_tier", "normal")
    colour = _COLOUR.get(tier, 0x5865F2)
    skills = job.get("skills") or "Python, Backend"

    embed = {
        "title":       "🚀 NEW SOFTWARE DEVELOPMENT (PYTHON) JOB FOUND",
        "color":       colour,
        "url":         job.get("job_url", ""),
        "fields": [
            {"name": "Position",  "value": job.get("job_title", "N/A"), "inline": False},
            {"name": "Company",   "value": job.get("company", "N/A"),   "inline": True},
            {"name": "Location",  "value": job.get("location", "Remote"), "inline": True},
            {"name": "Skills",    "value": skills,                       "inline": False},
            {"name": "Source",    "value": job.get("source", "N/A").replace("_", " ").title(),
                                                                          "inline": True},
            {"name": "Posted",    "value": _format_posted(job),           "inline": True},
            {"name": "Score",     "value": str(job.get("score", 0)),       "inline": True},
        ],
        "footer": {"text": "JobAlertBot • Apply now before it expires!"},
    }

    # Make the apply URL a clickable field if different from embed url
    url = job.get("job_url", "")
    if url:
        embed["fields"].append({"name": "Apply", "value": f"[Click here to apply]({url})", "inline": False})

    return embed


def _send_payload(payload: dict) -> bool:
    if not DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL not configured.")
        return False
    try:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=_TIMEOUT,
        )
        if resp.status_code in (200, 204):
            return True
        logger.warning("Discord responded %s: %s", resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as exc:
        logger.error("Discord send error: %s", exc)
        return False


def _send_text(content: str) -> bool:
    return _send_payload({"content": content})


def send_jobs(discord_jobs: list[dict], overflow_count: int = 0) -> int:
    """
    Send job notifications to Discord.

    discord_jobs   — pre-sorted list of jobs destined for Discord
    overflow_count — number of additional jobs in Gmail digest

    Returns number of successfully sent messages.
    """
    if not discord_jobs:
        return 0

    top_jobs = discord_jobs[:DISCORD_MAX_JOBS]
    sent = 0

    for job in top_jobs:
        embed   = _build_embed(job)
        payload = {"embeds": [embed]}
        if _send_payload(payload):
            sent += 1
            logger.info("Discord ✓  %s @ %s", job.get("job_title"), job.get("company"))
        else:
            logger.warning("Discord ✗  %s @ %s", job.get("job_title"), job.get("company"))

    # Overflow notice
    remaining = len(discord_jobs) - DISCORD_MAX_JOBS + overflow_count
    if remaining > 0:
        msg = (
            f"📬 **… and {remaining} more job{'s' if remaining > 1 else ''} found!**\n"
            "Check your Gmail inbox for the full digest."
        )
        _send_text(msg)

    return sent