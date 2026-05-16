"""
filters/keyword_filter.py — Keyword-based relevance gate.

A job passes when:
  1. Its title/description contains at least ONE include keyword.
  2. Its title/description contains at least ONE level keyword
     — OR the source is a junior-implied platform (e.g. OnlineJobs.ph).
  3. Its location/description contains at least ONE location keyword
     — OR the source is a remote-only platform (e.g. OnlineJobs.ph, RemoteOK).
  4. Its title/description does NOT contain any exclude keyword.
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
)

logger = logging.getLogger(__name__)


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
    title    = _lower(job.get("job_title", ""))
    desc     = _lower(job.get("description", ""))
    location = _lower(job.get("location", ""))
    source   = _lower(job.get("source", "")).replace(" ", "_")
    combined = f"{title} {desc}"

    # ── Hard exclusion first (fastest gate)
    if _matches_exclude(combined, EXCLUDE_KEYWORDS):
        logger.debug("EXCLUDED (senior/lead/etc.): %s", job.get("job_title"))
        return False

    # ── Must match a tech keyword
    if not _matches_any(combined, INCLUDE_KEYWORDS):
        logger.debug("EXCLUDED (no tech keyword): %s", job.get("job_title"))
        return False

    # ── Must match a level keyword
    # Skip this check for junior-implied sources — their entire platform
    # targets entry-level/freelance workers so the keyword may not appear
    if source not in JUNIOR_IMPLIED_SOURCES:
        if not _matches_any(combined, LEVEL_KEYWORDS):
            logger.debug("EXCLUDED (no level keyword): %s", job.get("job_title"))
            return False

    # ── Must be remote/hybrid
    # Skip this check for remote-only sources — every job on them is remote
    # by definition so requiring the keyword would wrongly reject valid jobs
    if source not in REMOTE_ONLY_SOURCES:
        location_text = f"{location} {combined}"
        if not _matches_any(location_text, LOCATION_KEYWORDS):
            logger.debug("EXCLUDED (not remote/hybrid): %s", job.get("job_title"))
            return False

    return True