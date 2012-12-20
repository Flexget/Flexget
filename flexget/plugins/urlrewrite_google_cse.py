from __future__ import unicode_literals, division, absolute_import
import re
import urllib2
import logging
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.plugin import *
from flexget.utils.soup import get_soup
from flexget.utils.tools import urlopener

log = logging.getLogger('google_cse')


class UrlRewriteGoogleCse:
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
            req = urllib2.Request(entry['url'], None, txheaders)
            page = urlopener(req, log)
            soup = get_soup(page)
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

register_plugin(UrlRewriteGoogleCse, 'google_cse', groups=['urlrewriter'])
