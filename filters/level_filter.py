"""
filters/level_filter.py — Freshness evaluation.

Pipeline step: runs BEFORE duplicate check and scoring.

Returns one of:
    "high"    → 0-2 days   → Discord priority
    "normal"  → 3-7 days   → Discord
    "low"     → 8-14 days  → Gmail digest
    "reject"  → >14 days   → discard
    "unknown" → no date    → handled by source-reliability rule
"""

import logging
from datetime import datetime, timezone
from config import (
    HIGH_RELIABILITY_SOURCES,
    FRESHNESS_REJECT_DAYS,
    FRESHNESS_DISCORD_MAX_DAYS,
)

logger = logging.getLogger(__name__)


def evaluate_freshness(job: dict) -> str:
    """
    Determine the freshness tier of a job.

    job must have:
        posted_days : int | None   — age of posting in days
        source      : str          — scraper source identifier
    """
    posted_days: int | None = job.get("posted_days")
    source: str = (job.get("source") or "").lower().replace(" ", "_")

    # ── Unknown date handling
    if posted_days is None:
        if source in HIGH_RELIABILITY_SOURCES:
            logger.debug(
                "Missing date from high-reliability source (%s): treating as 'normal'",
                source,
            )
            return "normal"
        else:
            logger.debug(
                "Missing date from low-reliability source (%s): rejected",
                source,
            )
            return "reject"

    # ── Hard rejection
    if posted_days > FRESHNESS_REJECT_DAYS:
        logger.debug("REJECTED (too old, %d days): %s", posted_days, job.get("job_title"))
        return "reject"

    # ── Tiered
    if posted_days <= 2:
        return "high"
    if posted_days <= FRESHNESS_DISCORD_MAX_DAYS:
        return "normal"
    return "low"   # 8-14 days → Gmail


def freshness_bonus(tier: str) -> int:
    """Return the scoring bonus for a freshness tier."""
    from config import FRESHNESS_BONUS
    return FRESHNESS_BONUS.get(tier, 0)


def notification_channel(tier: str) -> str:
    """Map freshness tier to notification channel."""
    if tier in ("high", "normal"):
        return "discord"
    if tier == "low":
        return "gmail"
    return "discard"