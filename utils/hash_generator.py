"""
utils/hash_generator.py — Deterministic job deduplication key.
"""

import hashlib
import re


def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def generate_hash(job_title: str, company: str, job_url: str) -> str:
    """
    Return a short SHA-256 hex digest that uniquely identifies a job post.
    Uses title + company + URL so that the same role at different companies
    (or the same company posting the same role on multiple boards) remains
    distinct.
    """
    raw = _normalise(job_title) + "|" + _normalise(company) + "|" + job_url.strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:32]