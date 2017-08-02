from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup
from flexget.utils.search import normalize_unicode

from requests.exceptions import RequestException

log = logging.getLogger('rlsbb')


class UrlRewriteAllyoulike(object):
    """
    allyoulike.com urlrewriter
    Version 0.1

    Rewrites urls for allyoulike.com

    On allyoulike, each link points to a page which contains the links to the actual files. 
    Often these pages contain links to more than one quality (for example 1080p, 720p etc.).
    The plugin chooses the set of links with the most files which should translate into the
    Best quality movie.

    There is no configuration for this plugin.

    If more than one valid link is found, the url of the entry is rewritten to
    the first link found. The complete list of valid links is placed in the
    'urls' field of the entry.

    Therefore, it is recommended, that you configure your output to use the
    'urls' field instead of the 'url' field.

    For example, to use jdownloader 2 as output, you would use the exec plugin:
    exec:
      - echo "text={{urls}}" >> "/path/to/jd2/folderwatch/{{title}}.crawljob"

    The plugin is intended to be used in conjunction with the html plugin.

    Example configuration for the html plugin:

    html:
      url: "http://www.allyoulike.com/category/movies/"
      title_from: link
      links_re:
        - allyoulike.com/\d*/(?!renew-or-purchase|for-vip-members-only)[^/]*/$
    """

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        rewritable_regex = '^https?:\/\/(www.)?allyoulike\.com\/.*'
        return re.match(rewritable_regex, url) is not None

    def _get_soup(self, task, url):
        try:
            page = task.requests.get(url)
        except RequestException as e:
            raise UrlRewritingError(str(e))
        try:
            return get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(str(e))

    @plugin.internet(log)
    # urlrewriter API
    def url_rewrite(self, task, entry):
        soup = self._get_soup(task, entry['url'])

        link_re = re.compile('rarefile\.net.*\.rar$')

        # grab links from the main entry:
        blog_entry = soup.find('div', class_="entry")
        num_links = 0
        link_list = None
        for paragraph in blog_entry.find_all('p'):
            links = paragraph.find_all('a', href=link_re)
            if len(links) > num_links:
                link_list = links
                num_links = len(links)
        if 'urls' in entry:
            urls = list(entry['urls'])
        else:
            urls = []
        if link_list is not None:
            for link in link_list:
                urls.append(normalize_unicode(link['href']))
        else:
            raise UrlRewritingError('No useable links found at %s' % entry['url'])

        num_links = len(urls)
        log.verbose('Found %d links at %s.', num_links, entry['url'])
        if num_links:
            entry['urls'] = urls
            entry['url'] = urls[0]
        else:
            raise UrlRewritingError('No useable links found at %s' % entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteAllyoulike, 'allyoulike', interfaces=['urlrewriter'], api_ver=2)
