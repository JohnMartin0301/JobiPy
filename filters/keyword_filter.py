"""
filters/keyword_filter.py — Keyword-based relevance gate.

A job passes when:
  1. Its title/description contains at least ONE include keyword.
  2. Its title/description contains at least ONE level keyword.
  3. Its location/description contains at least ONE location keyword.
  4. Its title/description does NOT contain any exclude keyword.
"""

import re
import logging
from config import (
    INCLUDE_KEYWORDS,
    LEVEL_KEYWORDS,
    LOCATION_KEYWORDS,
    EXCLUDE_KEYWORDS,
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
        job_title, description, location, company
    """
    title    = _lower(job.get("job_title", ""))
    desc     = _lower(job.get("description", ""))
    location = _lower(job.get("location", ""))
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
    if not _matches_any(combined, LEVEL_KEYWORDS):
        logger.debug("EXCLUDED (no level keyword): %s", job.get("job_title"))
        return False

    # ── Must be remote/hybrid
    location_text = f"{location} {combined}"
    if not _matches_any(location_text, LOCATION_KEYWORDS):
        logger.debug("EXCLUDED (not remote/hybrid): %s", job.get("job_title"))
        return False

    return True