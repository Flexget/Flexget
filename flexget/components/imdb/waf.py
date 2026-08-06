"""AWS WAF challenge handling for IMDB requests."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from loguru import logger

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


def is_waf_challenge(response: Any) -> bool:
    if response.status_code == 202:
        return True
    if response.headers.get('x-amzn-waf-action') == 'challenge':
        return True
    return bool(response.text and 'window.gokuProps' in response.text)


def solve_waf(response: Any, domain: str = 'imdb.com') -> str:
    from flexget.components.imdb.awswaf.aws import AwsWaf

    goku, host = AwsWaf.extract(response.text)
    logger.debug('Solving AWS WAF challenge for {}', domain)
    token = AwsWaf(goku, host, domain, IMDB_USER_AGENT)()
    logger.debug('AWS WAF challenge solved for {}', domain)
    return token


def imdb_get(url: str, *, raise_status: bool = True, **kwargs) -> Response:
    """GET an IMDB page, solving AWS WAF challenges when needed."""
    if _domain_limiter is not None:
        _domain_limiter()

    session = _get_session()
    headers = kwargs.pop('headers', None)
    req_headers = {**session.headers, **headers} if headers else None

    response = session.get(url, headers=req_headers, **kwargs)
    if is_waf_challenge(response):
        token = solve_waf(response)
        session.cookies.set('aws-waf-token', token, domain='.imdb.com')
        response = session.get(url, headers=req_headers, **kwargs)

    if raise_status and response.status_code >= 400:
        response.raise_for_status()

    return response
