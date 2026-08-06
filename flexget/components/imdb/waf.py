"""AWS WAF challenge handling for IMDB requests."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from loguru import logger

from flexget.utils.waf import waf_get

if TYPE_CHECKING:
    from curl_cffi.requests import Response

logger = logger.bind(name='imdb.waf')

IMDB_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
)

IMDB_BROWSER_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': IMDB_USER_AGENT,
}

_session = None
_session_lock = threading.Lock()
_domain_limiter = None


def _get_session():
    from curl_cffi import requests as curl_requests

    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = curl_requests.Session(impersonate='chrome')
                _session.headers.update(IMDB_BROWSER_HEADERS)
    return _session


def set_domain_limiter(limiter) -> None:
    """Register a rate limiter to run before each IMDB page request."""
    global _domain_limiter
    _domain_limiter = limiter


def imdb_get(url: str, *, raise_status: bool = True, **kwargs) -> Response:
    """GET an IMDB page, solving AWS WAF challenges when needed."""
    return waf_get(
        _get_session(),
        url,
        domain='imdb.com',
        cookie_domain='.imdb.com',
        user_agent=IMDB_USER_AGENT,
        limiter=_domain_limiter,
        raise_status=raise_status,
        **kwargs,
    )
