"""
scrapers/remoterocketship.py — Remote Rocketship scraper.

Remote Rocketship (remoterocketship.com) is a curated remote job board
that aggregates listings from company career pages across the web.

Strategy:
  The site renders job cards in HTML. We hit their search/filter
  endpoint directly with keyword parameters and parse the results
  with BeautifulSoup. No login required for public listings.

Search URL pattern:
  https://remoterocketship.com/jobs?keyword=python&type=junior
"""

import time
import logging
import requests
from urllib.parse import urlencode, urljoin
from bs4 import BeautifulSoup

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE      = "remoterocketship"
_BASE_URL    = "https://remoterocketship.com"
_SEARCH_URL  = "https://remoterocketship.com/jobs"
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
    "Referer":         "https://remoterocketship.com/",
}

_SEARCH_QUERIES = [
    "python",
    "flask",
    "fastapi",
    "python backend",
    "python junior",
    "python intern",
    "python automation",
    "backend engineer python",
]


def _build_url(keyword: str) -> str:
    # Remote Rocketship uses /jobs?keyword=... OR /jobs/keyword
    params = {"keyword": keyword, "remote": "true"}
    return f"{_SEARCH_URL}?{urlencode(params)}"


def _fetch_page(keyword: str) -> str | None:
    url = _build_url(keyword)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        logger.warning(
            "Remote Rocketship returned %s for '%s'", resp.status_code, keyword
        )
    except requests.RequestException as exc:
        logger.warning("Remote Rocketship fetch error for '%s': %s", keyword, exc)
    return None


def _parse_jobs(html: str) -> list[dict]:
    """Parse job cards from Remote Rocketship search results."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Primary selectors — Remote Rocketship job cards
    cards = soup.select(
        "div.job-card, "
        "div[class*='JobCard'], "
        "div[class*='job_card'], "
        "article[class*='job'], "
        "li[class*='job'], "
        "div[class*='listing']"
    )

    # Fallback — find all links pointing to /jobs/ detail pages
    if not cards:
        job_links = soup.select("a[href*='/jobs/']")
        for link in job_links:
            try:
                title = link.get_text(strip=True)
                href  = link.get("href", "")

                # Skip navigation links and non-job links
                if not title or len(title) < 5 or href in ("/jobs", "/jobs/"):
                    continue

                if not href.startswith("http"):
                    href = urljoin(_BASE_URL, href)

                # Try to get company/date from parent container
                parent  = link.find_parent(["div", "li", "article", "section"])
                company = ""
                date    = ""

                if parent:
                    company_el = parent.select_one(
                        "[class*='company'], [class*='employer'], "
                        "[class*='org'], span, p"
                    )
                    if company_el and company_el.get_text(strip=True) != title:
                        company = company_el.get_text(strip=True)

                    date_el = parent.select_one(
                        "[class*='date'], [class*='posted'], "
                        "[class*='ago'], time"
                    )
                    if date_el:
                        date = (
                            date_el.get("datetime")
                            or date_el.get_text(strip=True)
                        )

                jobs.append(
                    make_job(
                        job_title=title,
                        company=company,
                        location="Remote",
                        description=(
                            f"{title} {company} remote python backend junior "
                            "entry level work from home"
                        ),
                        source=_SOURCE,
                        job_url=href,
                        posted_date_raw=date or None,
                    )
                )
            except Exception as exc:
                logger.debug("Remote Rocketship link parse error: %s", exc)
        return jobs

    # Primary card parsing
    for card in cards:
        try:
            title_el   = card.select_one(
                "h2, h3, h4, "
                "[class*='title'], "
                "[class*='job-name'], "
                "[class*='position'], "
                "a[href*='/jobs/']"
            )
            company_el = card.select_one(
                "[class*='company'], "
                "[class*='employer'], "
                "[class*='org'], "
                "[class*='client']"
            )
            date_el    = card.select_one(
                "[class*='date'], "
                "[class*='posted'], "
                "[class*='ago'], "
                "time"
            )
            loc_el     = card.select_one(
                "[class*='location'], "
                "[class*='place'], "
                "[class*='region']"
            )
            link_el    = card.select_one("a[href*='/jobs/'], a[href]")

            title   = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            date    = ""
            loc     = loc_el.get_text(strip=True) if loc_el else "Remote"
            href    = ""

            if date_el:
                date = (
                    date_el.get("datetime")
                    or date_el.get_text(strip=True)
                )

            if link_el:
                href = link_el.get("href", "")
                if not href.startswith("http"):
                    href = urljoin(_BASE_URL, href)

            if not title or not href:
                continue

            # Ensure location signals remote — Remote Rocketship is
            # remote-only so we enrich the description accordingly
            jobs.append(
                make_job(
                    job_title=title,
                    company=company,
                    location=loc if loc else "Remote",
                    description=(
                        f"{title} {company} {loc} remote work from home "
                        "python backend junior entry level"
                    ),
                    source=_SOURCE,
                    job_url=href,
                    posted_date_raw=date or None,
                )
            )
        except Exception as exc:
            logger.debug("Remote Rocketship card parse error: %s", exc)

    return jobs


def scrape() -> list[dict]:
    """Entry point — returns all Remote Rocketship results."""
    all_jobs:  list[dict] = []
    seen_urls: set[str]   = set()

    for keyword in _SEARCH_QUERIES:
        html = _fetch_page(keyword)

        if not html:
            time.sleep(_QUERY_DELAY)
            continue

        for job in _parse_jobs(html):
            if job["job_url"] and job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                all_jobs.append(job)

        time.sleep(_QUERY_DELAY)

    logger.info("Remote Rocketship: %d raw results", len(all_jobs))
    return all_jobs