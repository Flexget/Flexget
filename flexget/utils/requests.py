from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.request import urlopen
from future.moves.urllib.parse import urlparse

import time
import logging
from datetime import timedelta, datetime

import requests
# Allow some request objects to be imported from here instead of requests
import warnings
from requests import RequestException, HTTPError

from flexget import __version__ as version
from flexget.utils.tools import parse_timedelta, TimedDict, timedelta_total_seconds

# If we use just 'requests' here, we'll get the logger created by requests, rather than our own
log = logging.getLogger('utils.requests')

# Don't emit info level urllib3 log messages or below
logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
# same as above, but for systems where urllib3 isn't part of the requests pacakge (i.e., Ubuntu)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Time to wait before trying an unresponsive site again
WAIT_TIME = timedelta(seconds=60)
# Remembers sites that have timed out
unresponsive_hosts = TimedDict(WAIT_TIME)


def is_unresponsive(url):
    """
    Checks if host of given url has timed out within WAIT_TIME

    :param url: The url to check
    :return: True if the host has timed out within WAIT_TIME
    :rtype: bool
    """
    host = urlparse(url).hostname
    return host in unresponsive_hosts


def set_unresponsive(url):
    """
    Marks the host of a given url as unresponsive

    :param url: The url that timed out
    """
    host = urlparse(url).hostname
    if host in unresponsive_hosts:
        # If somehow this is called again before previous timer clears, don't refresh
        return
    unresponsive_hosts[host] = True


class DomainLimiter(object):
    def __init__(self, domain):
        self.domain = domain

    def __call__(self):
        """This method will be called once before every request to the domain."""
        raise NotImplementedError


class TokenBucketLimiter(DomainLimiter):
    """
    A token bucket rate limiter for domains.
    
    New instances for the same domain will restore previous values.
    """
    # This is just an in memory cache right now, it works for the daemon, and across tasks in a single execution
    # but not for multiple executions via cron. Do we need to store this to db?
    state_cache = {}
    
    def __init__(self, domain, tokens, rate, wait=True):
        """
        :param int tokens: Size of bucket
        :param rate: Amount of time to accrue 1 token. Either `timedelta` or interval string.
        :param bool wait: If true, will wait for a token to be available. If false, errors when token is not available.
        """
        super(TokenBucketLimiter, self).__init__(domain)
        self.max_tokens = tokens
        self.rate = parse_timedelta(rate)
        self.wait = wait
        # Restore previous state for this domain, or establish new state cache
        self.state = self.state_cache.setdefault(domain, {'tokens': self.max_tokens, 'last_update': datetime.now()})

    @property
    def tokens(self):
        return min(self.max_tokens, self.state['tokens'])

    @tokens.setter
    def tokens(self, value):
        self.state['tokens'] = value

    @property
    def last_update(self):
        return self.state['last_update']

    @last_update.setter
    def last_update(self, value):
        self.state['last_update'] = value

    def __call__(self):
        if self.tokens < self.max_tokens:
            regen = (timedelta_total_seconds(datetime.now() - self.last_update) /
                     timedelta_total_seconds(self.rate))
            self.tokens += regen
        self.last_update = datetime.now()
        if self.tokens < 1:
            if not self.wait:
                raise RequestException('Requests to %s have exceeded their limit.' % self.domain)
            wait = timedelta_total_seconds(self.rate) * (1 - self.tokens)
            log.verbose('Waiting %.2f seconds until next request to %s' % (wait, self.domain))
            # Sleep until it is time for the next request
            time.sleep(wait)
        self.tokens -= 1


class TimedLimiter(TokenBucketLimiter):
    """Enforces a minimum interval between requests to a given domain."""
    def __init__(self, domain, interval):
        super(TimedLimiter, self).__init__(domain, 1, interval)


def _wrap_urlopen(url, timeout=None):
    """
    Handles alternate schemes using urllib, wraps the response in a requests.Response

    This is not installed as an adapter in requests, since urls without network locations
    (e.g. file:///somewhere) will cause errors

    """
    try:
        raw = urlopen(url, timeout=timeout)
    except IOError as e:
        msg = 'Error getting %s: %s' % (url, e)
        log.error(msg)
        raise RequestException(msg)
    resp = requests.Response()
    resp.raw = raw
    # requests passes the `decode_content` kwarg to read
    orig_read = raw.read
    resp.raw.read = lambda size, **kwargs: orig_read(size)
    resp.status_code = raw.code or 200
    resp.headers = requests.structures.CaseInsensitiveDict(raw.headers)
    return resp


def limit_domains(url, limit_dict):
    """
    If this url matches a domain in `limit_dict`, run the limiter.

    This is separated in to its own function so that limits can be disabled during unit tests with VCR.
    """
    for domain, limiter in limit_dict.items():
        if domain in url:
            limiter()
            break


class Session(requests.Session):
    """
    Subclass of requests Session class which defines some of our own defaults, records unresponsive sites,
    and raises errors by default.

    """

    def __init__(self, timeout=30, max_retries=1, *args, **kwargs):
        """Set some defaults for our session if not explicitly defined."""
        super(Session, self).__init__(*args, **kwargs)
        self.timeout = timeout
        self.stream = True
        self.adapters['http://'].max_retries = max_retries
        # Stores min intervals between requests for certain sites
        self.domain_limiters = {}
        self.headers.update({'User-Agent': 'FlexGet/%s (www.flexget.com)' % version})

    def add_cookiejar(self, cookiejar):
        """
        Merges cookies from `cookiejar` into cookiejar for this session.

        :param cookiejar: CookieJar instance to add to the session.
        """
        for cookie in cookiejar:
            self.cookies.set_cookie(cookie)

    def set_domain_delay(self, domain, delay):
        """
        DEPRECATED, use `add_domain_limiter`
        Registers a minimum interval between requests to `domain`

        :param domain: The domain to set the interval on
        :param delay: The amount of time between requests, can be a timedelta or string like '3 seconds'
        """
        warnings.warn('set_domain_delay is deprecated, use add_domain_limiter', DeprecationWarning, stacklevel=2)
        self.domain_limiters[domain] = TimedLimiter(domain, delay)
            
    def add_domain_limiter(self, limiter):
        """
        Add a limiter to throttle requests to a specific domain.

        :param DomainLimiter limiter: The `DomainLimiter` to add to the session.
        """
        self.domain_limiters[limiter.domain] = limiter

    def request(self, method, url, *args, **kwargs):
        """
        Does a request, but raises Timeout immediately if site is known to timeout, and records sites that timeout.
        Also raises errors getting the content by default.

        :param bool raise_status: If True, non-success status code responses will be raised as errors (True by default)
        """

        # Raise Timeout right away if site is known to timeout
        if is_unresponsive(url):
            raise requests.Timeout('Requests to this site (%s) have timed out recently. Waiting before trying again.' %
                urlparse(url).hostname)

        # Run domain limiters for this url
        limit_domains(url, self.domain_limiters)

        kwargs.setdefault('timeout', self.timeout)
        raise_status = kwargs.pop('raise_status', True)

        # If we do not have an adapter for this url, pass it off to urllib
        if not any(url.startswith(adapter) for adapter in self.adapters):
            log.debug('No adaptor, passing off to urllib')
            return _wrap_urlopen(url, timeout=kwargs['timeout'])

        try:
            log.debug('Fetching %s' % url)
            result = super(Session, self).request(method, url, *args, **kwargs)
        except requests.Timeout:
            # Mark this site in known unresponsive list
            set_unresponsive(url)
            raise

        if raise_status:
            result.raise_for_status()

        return result


# Define some module level functions that use our Session, so this module can be used like main requests module
def request(method, url, **kwargs):
    s = kwargs.pop('session', Session())
    return s.request(method=method, url=url, **kwargs)


def head(url, **kwargs):
    """Sends a HEAD request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param kwargs: Optional arguments that ``request`` takes.
    """
    kwargs.setdefault('allow_redirects', True)
    return request('head', url, **kwargs)


def get(url, **kwargs):
    """Sends a GET request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param kwargs: Optional arguments that ``request`` takes.
    """
    kwargs.setdefault('allow_redirects', True)
    return request('get', url, **kwargs)


def post(url, data=None, **kwargs):
    """Sends a POST request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary or bytes to send in the body of the :class:`Request`.
    :param kwargs: Optional arguments that ``request`` takes.
    """
    return request('post', url, data=data, **kwargs)
