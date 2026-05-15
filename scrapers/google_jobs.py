"""
scrapers/google_jobs.py — Google Jobs scraper via SerpAPI-free approach.

Strategy:
  Google Jobs does not have a public API. We use the "htl?q=jobs" endpoint
  which returns a structured JSON payload that Google's own job-search UI
  consumes. This is a best-effort, unofficial approach and may break if
  Google changes its internal API.

  Queries are built for each keyword combination and paginated.
"""

import logging
import requests
from urllib.parse import urlencode, quote_plus

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE = "google_jobs"

_SEARCH_QUERIES = [
    "junior python developer remote",
    "entry level flask fastapi remote",
    "junior backend developer python remote philippines",
    "python automation intern wfh",
    "associate software engineer python remote",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = 15


def _search_google_jobs(query: str) -> list[dict]:
    """
    Hit Google's internal jobs endpoint for a single query string.
    Returns raw job dicts or empty list on failure.
    """
    # Use Google's "jobs" search via normal search with jobs structured data
    url = f"https://www.google.com/search?q={quote_plus(query)}&ibp=htl;jobs"
    jobs: list[dict] = []

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        # Google returns HTML for this endpoint; we parse job cards
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Google Jobs cards have data attributes with job info
        for card in soup.select("[data-hveid] li, [jsname='MItjob']"):
            title_el   = card.select_one("[class*='title'], h3, [role='heading']")
            company_el = card.select_one("[class*='company'], [class*='employer']")
            loc_el     = card.select_one("[class*='location']")
            date_el    = card.select_one("[class*='date'], [class*='posted']")
            link_el    = card.select_one("a[href]")

            title   = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc     = loc_el.get_text(strip=True) if loc_el else ""
            date    = date_el.get_text(strip=True) if date_el else ""
            href    = link_el["href"] if link_el else ""

            if not title:
                continue

            # Build direct Google Jobs URL when only a relative path is returned
            if href and not href.startswith("http"):
                href = "https://www.google.com" + href

            jobs.append(
                make_job(
                    job_title=title,
                    company=company,
                    location=loc or "Remote",
                    description=f"{title} {loc}",
                    source=_SOURCE,
                    job_url=href,
                    posted_date_raw=date or None,
                )
            )

    except Exception as exc:
        logger.warning("Google Jobs scrape error for '%s': %s", query, exc)

    return jobs


def _search_via_serpapi_free(query: str) -> list[dict]:
    """
    Fallback: use the free SerpApi-compatible endpoint from jobicy.com
    or a public Google Jobs JSON mirror if available.
    This is a no-cost placeholder that returns real results when the
    primary approach is blocked.
    """
    # Free alternative: jobs.github.com-style or adzuna free tier
    # Here we use RemoteOK free JSON API as an additional source
    jobs: list[dict] = []
    try:
        url = "https://remoteok.com/api"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        data = resp.json()
        for item in data[1:]:  # first element is legal notice
            tags = " ".join(item.get("tags", [])).lower()
            title = item.get("position", "")
            if not any(kw in tags or kw in title.lower()
                       for kw in ("python", "flask", "fastapi", "backend")):
                continue
            jobs.append(
                make_job(
                    job_title=title,
                    company=item.get("company", ""),
                    location="Remote",
                    description=item.get("description", "")[:500],
                    skills=", ".join(item.get("tags", [])),
                    source="remoteok",
                    job_url=item.get("url", ""),
                    posted_date_raw=item.get("date"),
                )
            )
    except Exception as exc:
        logger.warning("RemoteOK fallback error: %s", exc)
    return jobs


def scrape() -> list[dict]:
    """Entry point: return all Google Jobs results."""
    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    for query in _SEARCH_QUERIES:
        results = _search_google_jobs(query)
        for job in results:
            if job["job_url"] and job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                all_jobs.append(job)

    # Always supplement with RemoteOK (reliable free JSON API)
    for job in _search_via_serpapi_free(""):
        if job["job_url"] and job["job_url"] not in seen_urls:
            seen_urls.add(job["job_url"])
            all_jobs.append(job)

    logger.info("Google Jobs / RemoteOK: %d raw results", len(all_jobs))
    return all_jobs