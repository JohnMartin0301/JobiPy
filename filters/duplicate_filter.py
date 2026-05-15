"""
filters/duplicate_filter.py — In-memory + DB deduplication.

Uses database.is_duplicate() for persistence across runs,
plus an in-run set to avoid re-processing within the same batch.
"""

import logging
from database import is_duplicate

logger = logging.getLogger(__name__)

_seen_this_run: set[str] = set()


def reset_run_cache() -> None:
    """Call at the start of each scrape cycle to clear the in-memory set."""
    _seen_this_run.clear()


def is_new_job(hash_id: str) -> bool:
    """
    Return True if this job has NOT been seen before.
    Checks both the in-run cache and the SQLite database.
    """
    if hash_id in _seen_this_run:
        logger.debug("Duplicate (in-run cache): %s", hash_id)
        return False
    if is_duplicate(hash_id):
        logger.debug("Duplicate (database): %s", hash_id)
        return False
    _seen_this_run.add(hash_id)
    return True