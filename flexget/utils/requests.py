from __future__ import absolute_import
import urllib2
import time
import logging
from datetime import timedelta, datetime
from urlparse import urlparse
import requests
# Allow some request objects to be imported from here instead of requests
from requests import RequestException

# Don't emit info level urllib3 log messages or below
logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)

# Remembers sites that have timed out
unresponsive_hosts = {}
# Time to wait before trying an unresponsive site again
WAIT_TIME = timedelta(seconds=60)


def is_unresponsive(url):
    """
    Checks if host of given url has timed out within WAIT_TIME

    :param url: The url to check
    :return: True if the host has timed out within WAIT_TIME
    :rtype: bool
    """
    host = urlparse(url).hostname
    if host in unresponsive_hosts and unresponsive_hosts[host] + WAIT_TIME < datetime.now():
        return True
    return False


def set_unresponsive(url):
    """
    Marks the host of a given url as unresponsive

    :param url: The url that timed out
    """
    host = urlparse(url).hostname
    unresponsive_hosts[host] = datetime.now()


def cookies_for_url(url, cookiejar):
    """
    Returns a dict containing the cookies from `cookiejar` that apply to given `url`.

    :param str url: The url that cookies should apply to.
    :param CookieJar cookiejar: The CookieJar instance to get cookies from.
    :return: A dict with cookies that apply to given url.
    :rtype: dict
    """

    result = {}
    req = urllib2.Request(url)
    # The policy _now attribute must be set to prevent the _cookies_for_request from crashing.
    cookiejar._policy._now = int(time.time())
    for cookie in cookiejar._cookies_for_request(req):
        result[cookie.name] = cookie.value
    return result


class Session(requests.Session):
    """Subclass of requests Session class which defines some of our own defaults, records unresponsive sites,
    and raises errors by default."""

    def __init__(self, **kwargs):
        """Set some defaults for our session if not explicitly defined."""
        kwargs.setdefault('timeout', 15)
        kwargs.setdefault('config', {}).setdefault('max_retries', 1)
        requests.Session.__init__(self, **kwargs)
        self.cookiejar = None

    def add_cookiejar(self, cookiejar):
        """
        Add a CookieJar whose cookies will apply to this session. If the session already has a cookiejar set,
        the cookies will be merged together.

        :param cookiejar: CookieJar instance to add to the session.
        """
        if not self.cookiejar:
            self.cookiejar = cookiejar
        else:
            for cookie in cookiejar:
                self.cookiejar.set_cookie(cookie)

    def request(self, method, url, *args, **kwargs):
        """
        Does a request, but raises Timeout immediately if site is known to timeout, and records sites that timeout.
        Also raises errors getting the content by default.
        """

        # Raise Timeout right away if site is known to timeout
        if is_unresponsive(url):
            raise requests.Timeout('Requests to this site are known to timeout.')

        # Pop our custom keyword argument before calling super method
        raise_status = kwargs.pop('raise_status', True)
        cookiejar = kwargs.pop('cookiejar', None)

        # Construct a dict with all cookies that apply to this request
        all_cookies = {}
        if self.cookiejar:
            all_cookies.update(cookies_for_url(url, self.cookiejar))
        if self.cookies:
            all_cookies.update(self.cookies)
        if cookiejar:
            all_cookies.update(cookies_for_url(url, cookiejar))
        if kwargs.get('cookies'):
            all_cookies.update(kwargs['cookies'])
        kwargs['cookies'] = all_cookies

        try:
            result = requests.Session.request(self, method, url, *args, **kwargs)
        except requests.Timeout:
            # Mark this site in known unresponsive list
            set_unresponsive(url)
            raise

        # Raise errors unless told not to
        if raise_status:
            result.raise_for_status()

        return result


# Define some module level functions that use our Session, so this module can be used like main requests module
def request(method, url, **kwargs):
    s = kwargs.pop('session', Session())
    return s.request(method=method, url=url, **kwargs)


def get(url, **kwargs):
    """Sends a GET request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param **kwargs: Optional arguments that ``request`` takes.
    """
    kwargs.setdefault('allow_redirects', True)
    return request('get', url, **kwargs)


def post(url, data=None, **kwargs):
    """Sends a POST request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary or bytes to send in the body of the :class:`Request`.
    :param **kwargs: Optional arguments that ``request`` takes.
    """
    return request('post', url, data=data, **kwargs)
