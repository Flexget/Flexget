from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import parse_qs, urlparse

import re
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup

log = logging.getLogger('google')

requests = Session()
requests.headers.update({'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'})
requests.add_domain_limiter(TimedLimiter('imdb.com', '2 seconds'))


class UrlRewriteGoogleCse(object):
    """Google custom query urlrewriter."""

    # urlrewriter API
    def url_rewritable(self, task, entry):
        if entry['url'].startswith('http://www.google.com/cse?'):
            return True
        if entry['url'].startswith('http://www.google.com/custom?'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        try:
            # need to fake user agent
            txheaders = {'User-agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
            page = task.requests.get(entry['url'], headers=txheaders)
            soup = get_soup(page.text)
            results = soup.find_all('a', attrs={'class': 'l'})
            if not results:
                raise UrlRewritingError('No results')
            for res in results:
                url = res.get('href')
                url = url.replace('/interstitial?url=', '')
                # generate match regexp from google search result title
                regexp = '.*'.join([x.contents[0] for x in res.find_all('em')])
                if re.match(regexp, entry['title']):
                    log.debug('resolved, found with %s' % regexp)
                    entry['url'] = url
                    return
            raise UrlRewritingError('Unable to resolve')
        except Exception as e:
            raise UrlRewritingError(e)


class UrlRewriteGoogle(object):
    # urlrewriter API

    def url_rewritable(self, task, entry):
        if entry['url'].startswith('https://www.google.com/search?q='):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        log.debug('Requesting %s' % entry['url'])
        page = requests.get(entry['url'])
        soup = get_soup(page.text)

        for link in soup.findAll('a', attrs={'href': re.compile(r'^/url')}):
            # Extract correct url from google internal link
            href = 'http://google.com' + link['href']
            args = parse_qs(urlparse(href).query)
            href = args['q'][0]

            # import IPython; IPython.embed()
            # import sys
            # sys.exit(1)
            # href = link['href'].lstrip('/url?q=').split('&')[0]

            # Test if entry with this url would be recognized by some urlrewriter
            log.trace('Checking if %s is known by some rewriter' % href)
            fake_entry = {'title': entry['title'], 'url': href}
            urlrewriting = plugin.get_plugin_by_name('urlrewriting')
            if urlrewriting['instance'].url_rewritable(task, fake_entry):
                log.debug('--> rewriting %s (known url pattern)' % href)
                entry['url'] = href
                return
            else:
                log.debug('<-- ignoring %s (unknown url pattern)' % href)
        raise UrlRewritingError('Unable to resolve')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteGoogleCse, 'google_cse', groups=['urlrewriter'], api_ver=2)
    plugin.register(UrlRewriteGoogle, 'google', groups=['urlrewriter'], api_ver=2)
