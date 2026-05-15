"""
scrapers/onlinejobs.py — OnlineJobs.ph scraper.

OnlineJobs.ph is the largest Philippine-focused remote job board.
All jobs on this platform are inherently remote/online — zero office roles.

Strategy:
    Parse the public HTML job search page. No login required.

Search URL:
    https://www.onlinejobs.ph/jobseekers/jobsearch?jobKeyword=python&jobLocation=0
    jobLocation=0 = anywhere / remote
"""

import time
import logging
import requests
from urllib.parse import urlencode, urljoin
from bs4 import BeautifulSoup

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE      = "onlinejobs_ph"
_BASE_URL    = "https://www.onlinejobs.ph"
_SEARCH_URL  = "https://www.onlinejobs.ph/jobseekers/jobsearch"
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
    "Referer":         "https://www.onlinejobs.ph/",
}

_SEARCH_TERMS = [
    "python developer",
    "python flask",
    "fastapi developer",
    "backend developer python",
    "automation engineer python",
    "software engineer python",
    "junior python",
    "entry level python",
]


def _build_url(keyword: str) -> str:
    params = {"jobKeyword": keyword, "jobLocation": 0}
    return f"{_SEARCH_URL}?{urlencode(params)}"


def _fetch_page(keyword: str) -> str | None:
    url = _build_url(keyword)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        logger.warning("OnlineJobs.ph returned %s for '%s'", resp.status_code, keyword)
    except requests.RequestException as exc:
        logger.warning("OnlineJobs.ph fetch error for '%s': %s", keyword, exc)
    return None


def _parse_jobs(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Primary selectors
    cards = soup.select(
        "div.job-post, "
        "div[class*='jobpost'], "
        "article.job, "
        "div.list-group-item, "
        "div[id*='job']"
    )

    # Fallback — grab any link pointing to a job detail page
    if not cards:
        for link in soup.select("a[href*='/jobseekers/job/']"):
            try:
                title = link.get_text(strip=True)
                href  = link.get("href", "")
                if not title or len(title) < 3:
                    continue
                if not href.startswith("http"):
                    href = urljoin(_BASE_URL, href)

                parent  = link.find_parent(["div", "li", "article"])
                company, date = "", ""
                if parent:
                    co_el = parent.select_one(
                        "[class*='company'], [class*='employer'], small, span"
                    )
                    if co_el:
                        company = co_el.get_text(strip=True)
                    dt_el = parent.select_one(
                        "[class*='date'], [class*='posted'], time"
                    )
                    if dt_el:
                        date = dt_el.get_text(strip=True)

                jobs.append(make_job(
                    job_title=title,
                    company=company,
                    location="Remote / Online — Philippines",
                    description=(
                        f"{title} {company} remote online "
                        "work from home philippines python junior entry level"
                    ),
                    source=_SOURCE,
                    job_url=href,
                    posted_date_raw=date or None,
                ))
            except Exception as exc:
                logger.debug("OnlineJobs.ph link parse error: %s", exc)
        return jobs

    # Primary card parsing
    for card in cards:
        try:
            title_el   = card.select_one(
                "h2, h3, h4, [class*='title'], "
                "[class*='job-name'], a[href*='/jobseekers/job/']"
            )
            company_el = card.select_one(
                "[class*='company'], [class*='employer'], [class*='client']"
            )
            date_el    = card.select_one(
                "[class*='date'], [class*='posted'], time, [class*='ago']"
            )
            link_el    = card.select_one("a[href*='/jobseekers/job/']")

            title   = title_el.get_text(strip=True)  if title_el   else ""
            company = company_el.get_text(strip=True) if company_el else ""
            date    = date_el.get_text(strip=True)    if date_el    else ""
            href    = ""

            if link_el:
                href = link_el.get("href", "")
                if not href.startswith("http"):
                    href = urljoin(_BASE_URL, href)

            if not title or not href:
                continue

            jobs.append(make_job(
                job_title=title,
                company=company,
                location="Remote / Online — Philippines",
                description=(
                    f"{title} {company} remote online "
                    "work from home philippines python junior entry level"
                ),
                source=_SOURCE,
                job_url=href,
                posted_date_raw=date or None,
            ))
        except Exception as exc:
            logger.debug("OnlineJobs.ph card parse error: %s", exc)

    return jobs


def scrape() -> list[dict]:
    """Entry point — returns all OnlineJobs.ph results."""
    all_jobs:  list[dict] = []
    seen_urls: set[str]   = set()

    for term in _SEARCH_TERMS:
        html = _fetch_page(term)
        if not html:
            time.sleep(_QUERY_DELAY)
            continue
        for job in _parse_jobs(html):
            if job["job_url"] and job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                all_jobs.append(job)
        time.sleep(_QUERY_DELAY)

    logger.info("OnlineJobs.ph: %d raw results", len(all_jobs))
    return all_jobs