"""Generic AWS WAF challenge handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from flexget.utils.waf.aws import AwsWaf

if TYPE_CHECKING:
    from curl_cffi.requests import Response, Session

logger = logger.bind(name='utils.waf')

__all__ = ['AwsWaf', 'is_waf_challenge', 'solve_waf', 'waf_get']


def is_waf_challenge(response: Any) -> bool:
    if response.status_code == 202:
        return True
    if response.headers.get('x-amzn-waf-action') == 'challenge':
        return True
    return bool(response.text and 'window.gokuProps' in response.text)


def solve_waf(response: Any, domain: str, user_agent: str | None = None) -> str:
    goku, host = AwsWaf.extract(response.text)
    logger.debug('Solving AWS WAF challenge for {}', domain)
    kwargs = {'user_agent': user_agent} if user_agent else {}
    token = AwsWaf(goku, host, domain, **kwargs)()
    logger.debug('AWS WAF challenge solved for {}', domain)
    return token


def waf_get(
    session: Session,
    url: str,
    *,
    domain: str,
    cookie_domain: str | None = None,
    user_agent: str | None = None,
    limiter=None,
    raise_status: bool = True,
    **kwargs,
) -> Response:
    """GET a URL, solving an AWS WAF challenge and retrying once if one is served."""
    if limiter is not None:
        limiter()

    headers = kwargs.pop('headers', None)
    req_headers = {**session.headers, **headers} if headers else None

    response = session.get(url, headers=req_headers, **kwargs)
    if is_waf_challenge(response):
        token = solve_waf(response, domain, user_agent)
        session.cookies.set('aws-waf-token', token, domain=cookie_domain or f'.{domain}')
        response = session.get(url, headers=req_headers, **kwargs)

    if raise_status and response.status_code >= 400:
        response.raise_for_status()

    return response
