"""
utils/url_validator.py — Lightweight HTTP reachability check.

Rules:
  • Must return HTTP 200
  • Must respond within URL_TIMEOUT_SECONDS
  • Redirects are followed; only the final status matters
  • Returns False for any network error or non-200 status
"""

import logging
import requests
from config import URL_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (compatible; JobAlertBot/1.0; "
            "+https://github.com/your-org/job-alert-bot)"
        )
    }
)


def is_valid_url(url: str) -> bool:
    """Return True if the URL is reachable and returns HTTP 200."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        resp = _SESSION.head(
            url,
            allow_redirects=True,
            timeout=URL_TIMEOUT_SECONDS,
        )
        if resp.status_code == 405:
            # Some servers reject HEAD; fall back to GET with streaming
            resp = _SESSION.get(
                url,
                allow_redirects=True,
                timeout=URL_TIMEOUT_SECONDS,
                stream=True,
            )
        valid = resp.status_code == 200
        if not valid:
            logger.debug("URL rejected (status %s): %s", resp.status_code, url)
        return valid
    except requests.RequestException as exc:
        logger.debug("URL validation error for %s: %s", url, exc)
        return False