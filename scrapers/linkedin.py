"""
scrapers/linkedin.py — LinkedIn Jobs scraper via Playwright.

LinkedIn requires JavaScript rendering. We use Playwright in headless
mode to fetch the public job search page (no login required for search
result listings).

Note: LinkedIn aggressively rate-limits and CAPTCHAs bots. This scraper
uses realistic delays and a single browser context per run.
"""

import time
import logging
from typing import Optional

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE = "linkedin"

_SEARCH_URLS = [
    (
        "https://www.linkedin.com/jobs/search/?keywords=junior%20python%20developer&f_WT=2&f_E=1%2C2&sortBy=DD",
        "junior python developer remote entry level"
    ),
    (
        "https://www.linkedin.com/jobs/search/?keywords=entry%20level%20flask%20fastapi&f_WT=2&f_E=1%2C2&sortBy=DD",
        "entry level flask fastapi remote junior"
    ),
    (
        "https://www.linkedin.com/jobs/search/?keywords=python%20backend%20intern%20junior&f_WT=2&f_E=1%2C2&sortBy=DD",
        "python backend intern junior remote entry level"
    ),
]
# f_WT=2 → Remote   f_E=1,2 → Internship + Entry Level   sortBy=DD → Date


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _scrape_url(page, url: str, search_context: str = "") -> list[dict]:
    """Scrape a single LinkedIn search URL using an open Playwright page."""
    jobs = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(3)  # let JS render

        # Scroll to load more cards
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(1)

        cards = page.query_selector_all(".base-card, .job-search-card")
        for card in cards:
            try:
                title_el   = card.query_selector(".base-search-card__title, h3")
                company_el = card.query_selector(".base-search-card__subtitle, h4")
                loc_el     = card.query_selector(".job-search-card__location")
                date_el    = card.query_selector("time")
                link_el    = card.query_selector("a.base-card__full-link, a[href*='/jobs/view']")

                title   = title_el.inner_text().strip() if title_el else ""
                company = company_el.inner_text().strip() if company_el else ""
                loc     = loc_el.inner_text().strip() if loc_el else "Remote"
                date    = date_el.get_attribute("datetime") if date_el else ""
                href    = link_el.get_attribute("href") if link_el else ""

                if not title:
                    continue

                # Enrich description with search context so keyword filter
                # can match against python/junior/remote terms even when
                # they don't appear in the scraped title/company/location
                enriched_desc = f"{title} {company} {loc} {search_context}"

                jobs.append(
                    make_job(
                        job_title=title,
                        company=company,
                        location=loc if loc else "Remote",
                        description=enriched_desc,
                        source=_SOURCE,
                        job_url=href or url,
                        posted_date_raw=date or None,
                    )
                )
            except Exception as exc:
                logger.debug("LinkedIn card parse error: %s", exc)
    except Exception as exc:
        logger.warning("LinkedIn page load error (%s): %s", url, exc)
    return jobs


def scrape() -> list[dict]:
    if not _playwright_available():
        logger.warning(
            "Playwright not installed. Skipping LinkedIn scraper. "
            "Run: pip install playwright && playwright install chromium"
        )
        return []

    from playwright.sync_api import sync_playwright
    from config import PLAYWRIGHT_HEADLESS

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for url, search_context in _SEARCH_URLS:
            for job in _scrape_url(page, url, search_context):
                if job["job_url"] not in seen_urls:
                    seen_urls.add(job["job_url"])
                    all_jobs.append(job)
            time.sleep(4)

        browser.close()

    logger.info("LinkedIn: %d raw results", len(all_jobs))
    return all_jobs