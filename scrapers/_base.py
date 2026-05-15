"""
scrapers/_base.py — Shared scraper utilities.

All scrapers produce a list of dicts conforming to this schema:

{
    "job_title"  : str,
    "company"    : str,
    "location"   : str,
    "description": str,       # raw text snippet
    "skills"     : str,       # comma-separated if known
    "source"     : str,       # e.g. "google_jobs"
    "job_url"    : str,
    "posted_date": str | None,  # ISO or human-readable
    "posted_days": int | None,  # computed age in days
}
"""

import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Relative date parser  ("2 days ago", "3 hours ago", etc.)
# ──────────────────────────────────────────────────────────────
_REL_PATTERNS = [
    (r"(\d+)\s+minute", lambda m: round(int(m.group(1)) / 1440, 2)),
    (r"(\d+)\s+hour",   lambda m: round(int(m.group(1)) / 24, 2)),
    (r"(\d+)\s+day",    lambda m: int(m.group(1))),
    (r"(\d+)\s+week",   lambda m: int(m.group(1)) * 7),
    (r"(\d+)\s+month",  lambda m: int(m.group(1)) * 30),
    (r"just now|today", lambda m: 0),
    (r"yesterday",      lambda m: 1),
]


def parse_relative_date(text: str) -> int | None:
    """
    Convert a human-readable relative date string to days (int).
    Returns None if the string cannot be parsed.
    """
    if not text:
        return None
    text = text.lower().strip()
    for pattern, calc in _REL_PATTERNS:
        m = re.search(pattern, text)
        if m:
            result = calc(m)
            return int(result) if isinstance(result, float) and result >= 1 else (
                0 if result < 1 else int(result)
            )
    return None


def parse_iso_date(text: str) -> int | None:
    """
    Parse an ISO-8601 date string and return the age in days.
    Returns None on failure.
    """
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            return max(0, delta.days)
        except ValueError:
            continue
    return None


def compute_posted_days(posted_date_raw: str | None) -> int | None:
    """
    Try relative parse first, then ISO parse.
    Returns None if both fail.
    """
    if not posted_date_raw:
        return None
    days = parse_relative_date(posted_date_raw)
    if days is None:
        days = parse_iso_date(posted_date_raw)
    return days


def make_job(
    *,
    job_title: str,
    company: str = "",
    location: str = "",
    description: str = "",
    skills: str = "",
    source: str,
    job_url: str,
    posted_date_raw: str | None = None,
) -> dict:
    """Factory that produces a normalised job dict."""
    posted_days = compute_posted_days(posted_date_raw)
    return {
        "job_title":   job_title.strip(),
        "company":     company.strip(),
        "location":    location.strip(),
        "description": description.strip(),
        "skills":      skills.strip(),
        "source":      source,
        "job_url":     job_url.strip(),
        "posted_date": posted_date_raw or "",
        "posted_days": posted_days,
    }