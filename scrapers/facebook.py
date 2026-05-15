"""
scrapers/facebook.py — Facebook Jobs scraper (best-effort, optional).

Facebook Jobs requires login and heavy JavaScript. This scraper uses
Playwright with stored cookies if available. If no cookies are found
it gracefully skips and returns an empty list.

To enable:
  1. Log into Facebook manually in Chromium.
  2. Export cookies to data/fb_cookies.json (use EditThisCookie extension).
  3. The scraper will load them on the next run.
"""

import json
import time
import logging
from pathlib import Path

from scrapers._base import make_job

logger = logging.getLogger(__name__)

_SOURCE = "facebook"
_COOKIES_PATH = Path("data/fb_cookies.json")
_SEARCH_URLS = [
    "https://www.facebook.com/jobs/?q=python%20junior",
    "https://www.facebook.com/jobs/?q=entry%20level%20python%20backend",
]


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def scrape() -> list[dict]:
    """Return Facebook job listings. Silently returns [] if not configured."""
    if not _playwright_available():
        logger.info("Playwright unavailable — Facebook scraper skipped.")
        return []

    if not _COOKIES_PATH.exists():
        logger.info(
            "No Facebook cookies found at %s — Facebook scraper skipped. "
            "Export cookies from a logged-in Facebook session to enable.",
            _COOKIES_PATH,
        )
        return []

    try:
        cookies = json.loads(_COOKIES_PATH.read_text())
    except Exception as exc:
        logger.warning("Could not read Facebook cookies: %s", exc)
        return []

    from playwright.sync_api import sync_playwright
    from config import PLAYWRIGHT_HEADLESS

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        for url in _SEARCH_URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                time.sleep(4)

                cards = page.query_selector_all("[data-testid='job-card'], [class*='job']")
                for card in cards:
                    try:
                        title_el   = card.query_selector("strong, h3")
                        company_el = card.query_selector("[class*='company'], [class*='employer']")
                        loc_el     = card.query_selector("[class*='location']")
                        link_el    = card.query_selector("a[href*='/jobs/']")

                        title   = title_el.inner_text().strip() if title_el else ""
                        company = company_el.inner_text().strip() if company_el else ""
                        loc     = loc_el.inner_text().strip() if loc_el else ""
                        href    = link_el.get_attribute("href") if link_el else ""
                        if href and not href.startswith("http"):
                            href = "https://www.facebook.com" + href

                        if not title:
                            continue

                        if href and href not in seen_urls:
                            seen_urls.add(href)
                            all_jobs.append(
                                make_job(
                                    job_title=title,
                                    company=company,
                                    location=loc or "Remote",
                                    description=f"{title} {company} {loc}",
                                    source=_SOURCE,
                                    job_url=href,
                                    posted_date_raw=None,
                                )
                            )
                    except Exception as exc:
                        logger.debug("Facebook card parse error: %s", exc)
            except Exception as exc:
                logger.warning("Facebook page error (%s): %s", url, exc)
            time.sleep(3)

        browser.close()

    logger.info("Facebook: %d raw results", len(all_jobs))
    return all_jobs