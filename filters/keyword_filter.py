"""
filters/keyword_filter.py — Keyword-based relevance gate.

A job passes when:
  1. Source is not in DISABLED_SOURCES.
  2. Its title OR description contains at least ONE Python-specific keyword.
  3. Its title/description contains at least ONE level keyword
     — OR the source is a junior-implied platform.
  4. Its location/description contains at least ONE location keyword
     — OR the source is a remote-only platform.
  5. Its title/description does NOT contain any exclude keyword.
"""

import re
import logging
from config import (
    INCLUDE_KEYWORDS,
    LEVEL_KEYWORDS,
    LOCATION_KEYWORDS,
    EXCLUDE_KEYWORDS,
    REMOTE_ONLY_SOURCES,
    JUNIOR_IMPLIED_SOURCES,
    DISABLED_SOURCES,
)

logger = logging.getLogger(__name__)

# Keywords that MUST appear in the job title specifically
# to ensure the role is genuinely Python/tech related
TITLE_KEYWORDS = [
    "python", "flask", "fastapi", "django",
    "backend", "software", "developer", "engineer",
    "automation", "api", "fullstack", "full stack",
    "programmer", "coding", "web dev",
]


def _lower(text: str) -> str:
    return (text or "").lower()


def _matches_any(haystack: str, keywords: list[str]) -> bool:
    return any(kw in haystack for kw in keywords)


def _matches_exclude(haystack: str, keywords: list[str]) -> bool:
    """
    Use word-boundary matching for exclusion so that e.g. 'sr.' or ' sr '
    don't accidentally match 'software'.
    """
    for kw in keywords:
        pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
        if re.search(pattern, haystack):
            return True
    return False


def passes_keyword_filter(job: dict) -> bool:
    """
    Return True if the job satisfies all keyword criteria.

    Expected job keys (all optional but at least some must be present):
        job_title, description, location, source, company
    """
    source   = _lower(job.get("source", "")).replace(" ", "_")
    title    = _lower(job.get("job_title", ""))
    desc     = _lower(job.get("description", ""))
    location = _lower(job.get("location", ""))
    combined = f"{title} {desc}"

    # ── Gate 0: skip disabled sources entirely
    if source in DISABLED_SOURCES:
        logger.debug("EXCLUDED (disabled source %s): %s", source, job.get("job_title"))
        return False

    # ── Gate 1: Hard exclusion (seniority + irrelevant industries)
    if _matches_exclude(combined, EXCLUDE_KEYWORDS):
        logger.debug("EXCLUDED (senior/lead/etc.): %s", job.get("job_title"))
        return False

    # ── Gate 2: Title must contain a tech/Python keyword
    # This is the strictest gate — the job TITLE itself must signal
    # it is a tech role, not just the description
    if not _matches_any(title, TITLE_KEYWORDS):
        logger.debug("EXCLUDED (title not tech): %s", job.get("job_title"))
        return False

    # ── Gate 3: Must match a Python-specific keyword in title or description
    if not _matches_any(combined, INCLUDE_KEYWORDS):
        logger.debug("EXCLUDED (no Python keyword): %s", job.get("job_title"))
        return False

    # ── Gate 4: Must match a level keyword
    # Skip for junior-implied sources
    if source not in JUNIOR_IMPLIED_SOURCES:
        if not _matches_any(combined, LEVEL_KEYWORDS):
            logger.debug("EXCLUDED (no level keyword): %s", job.get("job_title"))
            return False

    # ── Gate 5: Must be remote/hybrid
    # Skip for remote-only sources
    if source not in REMOTE_ONLY_SOURCES:
        location_text = f"{location} {combined}"
        if not _matches_any(location_text, LOCATION_KEYWORDS):
            logger.debug("EXCLUDED (not remote/hybrid): %s", job.get("job_title"))
            return False

    return True