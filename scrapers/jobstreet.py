"""
scrapers/jobstreet.py — JobStreet PH scraper.

JobStreet (Philippines) has a semi-public API endpoint used by their
own search UI. We replicate those requests directly.

Endpoint: https://ph.jobstreet.com/api/jobsearch/v5/jobs
"""

import time
import logging
import requests

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE      = "jobstreet"
_BASE_URL    = "https://ph.jobstreet.com"
_TIMEOUT     = 15
_QUERY_DELAY = 3

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer":         "https://ph.jobstreet.com/",
}

# JobStreet PH uses slug-based search URLs
# Format: /keyword-jobs?workarrangement=2 (2=Remote, 3=Hybrid)
_SEARCH_SLUGS = [
    "junior-python-developer",
    "entry-level-python",
    "python-flask",
    "python-fastapi",
    "junior-backend-developer",
    "python-automation",
    "associate-software-engineer-python",
    "python-intern",
]


def _fetch(slug: str) -> str | None:
    # JobStreet search URL format: /keyword-jobs?workarrangement=2,3
    url = f"{_BASE_URL}/{slug}-jobs?workarrangement=2,3&sortmode=ListedDate"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        logger.warning("JobStreet returned %s for '%s'", resp.status_code, slug)
    except Exception as exc:
        logger.warning("JobStreet fetch error for '%s': %s", slug, exc)
    return None


def _parse_response(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # JobStreet renders job cards with data attributes
    cards = soup.select(
        "article[data-job-id], "
        "div[data-job-id], "
        "[class*='job-card'], "
        "[class*='JobCard'], "
        "div[class*='result']"
    )

    # Fallback — find job links
    if not cards:
        job_links = soup.select("a[href*='/job/']")
        for link in job_links:
            try:
                title = link.get_text(strip=True)
                href  = link.get("href", "")
                if not href.startswith("http"):
                    href = f"{_BASE_URL}{href}"
                if not title or len(title) < 5:
                    continue
                parent  = link.find_parent(["article", "div", "li", "section"])
                company, date, loc = "", "", "Remote — Philippines"
                if parent:
                    co_el  = parent.select_one("[class*='company'], [class*='advertiser']")
                    dt_el  = parent.select_one("time, [class*='date'], [class*='listed']")
                    loc_el = parent.select_one("[class*='location']")
                    if co_el:  company = co_el.get_text(strip=True)
                    if dt_el:  date    = dt_el.get("datetime") or dt_el.get_text(strip=True)
                    if loc_el: loc     = loc_el.get_text(strip=True)
                jobs.append(make_job(
                    job_title=title, company=company, location=loc,
                    description=f"{title} {company} remote python junior entry level",
                    source=_SOURCE, job_url=href, posted_date_raw=date or None,
                ))
            except Exception as exc:
                logger.debug("JobStreet link parse error: %s", exc)
        return jobs

    for card in cards:
        try:
            title_el   = card.select_one("h1, h2, h3, [class*='title'], [class*='job-title']")
            company_el = card.select_one("[class*='company'], [class*='advertiser']")
            date_el    = card.select_one("time, [class*='date'], [class*='listed']")
            loc_el     = card.select_one("[class*='location']")
            link_el    = card.select_one("a[href*='/job/']")

            title   = title_el.get_text(strip=True)   if title_el   else ""
            company = company_el.get_text(strip=True)  if company_el else ""
            loc     = loc_el.get_text(strip=True)      if loc_el     else "Remote — Philippines"
            date    = ""
            href    = ""

            if date_el:
                date = date_el.get("datetime") or date_el.get_text(strip=True)
            if link_el:
                href = link_el.get("href", "")
                if not href.startswith("http"):
                    href = f"{_BASE_URL}{href}"

            if not title or not href:
                continue

            jobs.append(make_job(
                job_title=title, company=company, location=loc,
                description=f"{title} {company} remote python junior entry level",
                source=_SOURCE, job_url=href, posted_date_raw=date or None,
            ))
        except Exception as exc:
            logger.debug("JobStreet card parse error: %s", exc)

    return jobs


def scrape() -> list[dict]:
    all_jobs:  list[dict] = []
    seen_urls: set[str]   = set()

    for slug in _SEARCH_SLUGS:
        html = _fetch(slug)
        if not html:
            time.sleep(_QUERY_DELAY)
            continue
        for job in _parse_response(html):
            if job["job_url"] and job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                all_jobs.append(job)
        time.sleep(_QUERY_DELAY)

    logger.info("JobStreet: %d raw results", len(all_jobs))
    return all_jobs