"""
filters/scoring.py — Relevance scoring engine.

Score breakdown:
    +30  Python mentioned
    +20  Flask or FastAPI mentioned
    +20  Remote/WFH/hybrid
    +20  Junior / entry-level
    +15  Posted within 0–48 hours (freshness bonus set externally)
    +10  From LinkedIn / Indeed / JobStreet
    +0–15 Freshness bonus (injected from level_filter)
"""

import logging
from config import SCORE_WEIGHTS, GOOD_SOURCES_FOR_SCORE

logger = logging.getLogger(__name__)


def _lower(text: str) -> str:
    return (text or "").lower()


def score_job(job: dict, freshness_bonus: int = 0) -> int:
    """
    Compute and return an integer relevance score for a job dict.

    job expected keys:
        job_title, description, location, source, posted_days
    freshness_bonus: pre-computed bonus from level_filter.freshness_bonus()
    """
    title    = _lower(job.get("job_title", ""))
    desc     = _lower(job.get("description", ""))
    location = _lower(job.get("location", ""))
    source   = _lower(job.get("source", ""))
    days     = job.get("posted_days")

    combined = f"{title} {desc}"
    loc_full = f"{location} {combined}"

    score = 0

    # Tech keywords
    if "python" in combined:
        score += SCORE_WEIGHTS["python"]

    if "flask" in combined or "fastapi" in combined:
        score += SCORE_WEIGHTS["flask_fastapi"]

    # Location
    if any(kw in loc_full for kw in ("remote", "wfh", "work from home", "hybrid")):
        score += SCORE_WEIGHTS["remote"]

    # Level
    if any(kw in combined for kw in ("junior", "entry level", "entry-level",
                                      "associate", "fresh graduate", "intern",
                                      "no experience", "trainee", "graduate")):
        score += SCORE_WEIGHTS["junior"]

    # Freshness (0-48 h)
    if days is not None and days <= 2:
        score += SCORE_WEIGHTS["fresh_post"]

    # Source quality
    source_key = source.replace(" ", "_")
    if source_key in GOOD_SOURCES_FOR_SCORE:
        score += SCORE_WEIGHTS["good_source"]

    # Add tiered freshness bonus from level_filter
    score += freshness_bonus

    logger.debug("Score for '%s': %d", job.get("job_title"), score)
    return score