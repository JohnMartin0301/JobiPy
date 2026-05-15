"""
scrapers/indeed.py — Indeed job scraper (HTML parsing).

Indeed blocks heavy bot traffic. This scraper uses:
  1. Rotating user-agent headers
  2. Respectful delays
  3. HTML parsing of the public search results page

Targets: indeed.com (international) with location=remote
"""

import time
import logging
import requests
from urllib.parse import urlencode, quote_plus
from bs4 import BeautifulSoup

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE = "indeed"
_BASE_URL = "https://ph.indeed.com/jobs"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "none",
    "Referer":         "https://ph.indeed.com/",
}
_TIMEOUT     = 15
_PAGE_DELAY  = 3

_QUERIES = [
    ("junior python developer",          "remote"),
    ("entry level flask fastapi",        "remote"),
    ("python automation junior",         "remote"),
    ("backend developer intern python",  "remote"),
    ("associate software engineer python","remote"),
]


def _fetch_page(query: str, location: str, start: int = 0) -> str | None:
    params = {
        "q":       query,
        "l":       location,
        "start":   start,
        "fromage": 14,
        "sort":    "date",
        "sc":      "0kf:attr(DSQF7)jt(internship)jt(fulltime);",
    }
    url = f"{_BASE_URL}?{urlencode(params)}"
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        logger.warning("Indeed returned %s for '%s'", resp.status_code, query)
    except requests.RequestException as exc:
        logger.warning("Indeed fetch error: %s", exc)
    return None


def _parse_jobs(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for card in soup.select(
        "div.job_seen_beacon, "
        "div[class*='jobsearch-ResultsList'] > li, "
        "li[class*='css-']"
    ):
        try:
            title_el   = card.select_one("h2.jobTitle span, a.jcs-JobTitle, h2 a, [class*='jobTitle']")
            company_el = card.select_one("[data-testid='company-name'], span.companyName, [class*='company']")
            loc_el     = card.select_one("[data-testid='text-location'], div.companyLocation, [class*='location']")
            date_el    = card.select_one("span.date, [data-testid='myJobsStateDate'], [class*='date']")
            link_el    = card.select_one("h2.jobTitle a, a.jcs-JobTitle, a[id*='job']")

            title   = title_el.get_text(strip=True)   if title_el   else ""
            company = company_el.get_text(strip=True)  if company_el else ""
            loc     = loc_el.get_text(strip=True)      if loc_el     else "Remote"
            date    = date_el.get_text(strip=True)     if date_el    else ""
            href    = ""

            if link_el and link_el.get("href"):
                href = link_el["href"]
                if not href.startswith("http"):
                    href = "https://ph.indeed.com" + href

            if not title or not href:
                continue

            jobs.append(make_job(
                job_title=title, company=company, location=loc,
                description=f"{title} {company} {loc}",
                source=_SOURCE, job_url=href, posted_date_raw=date or None,
            ))
        except Exception as exc:
            logger.debug("Indeed card parse error: %s", exc)

    return jobs


def scrape() -> list[dict]:
    all_jobs:  list[dict] = []
    seen_urls: set[str]   = set()

    for query, location in _QUERIES:
        html = _fetch_page(query, location)
        if not html:
            continue
        for job in _parse_jobs(html):
            if job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                all_jobs.append(job)
        time.sleep(_PAGE_DELAY)

    logger.info("Indeed: %d raw results", len(all_jobs))
    return all_jobs