from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup
from flexget.entry import Entry
from flexget.utils.search import normalize_unicode

log = logging.getLogger('rmz')

class UrlRewriteRmz(object):
    """
    rmz.cr (rapidmoviez.com) urlrewriter
    Version 0.1
    
    Configuration

    url_re:
      - domain\.com

    Only add links that match any of the regular expressions listed under url_re.

    If more than one valid link is found, the url of the entry is rewritten to
    the first link found. The complete list of valid links is placed in the
    'urls' field of the entry.
    
    Therefore, it is recommended, that you configure your output to use the
    'urls' field instead of the 'url' field.
    
    For example, to use jdownloader 2 as output, you would use the exec plugin:
    exec:
      - echo "text={{urls}}" >> "/path/to/jd2/folderwatch/{{title}}.crawljob"
    """

    schema = {
        'type': 'object',
        'properties': {
            'links_re': {'type': 'array', 'items': {'format': 'regexp'} }
        },
        'additionalProperties': False
    }

    # Since the urlrewriter relies on a config, we need to create a default one
    config = {
        'links_re': None
    }

    #grab config
    def on_task_start(self, task, config):
        self.config = config

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        rewritable_regex = '^https?:\/\/(www.)?(rmz\.cr|rapidmoviez\.(com|eu))\/.*'
        if re.match(rewritable_regex, url):
            return True
        else:
            return False

    @plugin.internet(log)
   # urlrewriter API
    def url_rewrite(self, task, entry):
        try:
            page = task.requests.get(entry['url'])
        except Exception as e:
            raise UrlRewritingError(e)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)
        link_elements = soup.find_all('pre', class_='links')
        urls=[]
        for element in link_elements:
            urls.extend(element.text.splitlines())
        regexps = self.config.get('links_re', None)
        if regexps:
            log.debug('Using links_re filters: %s', str(regexps))
        else:
            log.debug('No link filters configured, using all found links.')
        for i in reversed(range(len(urls))):
            urls[i]=urls[i].encode('ascii','ignore')
            if regexps:
                accept = False
                for regexp in regexps:
                    if re.search(regexp, urls[i]):
                        accept = True
                        log.debug('Url: "%s" matched filter: %s', urls[i], regexp)
                        break
                if not accept:
                    log.debug('Url: "%s" does not match any of the given filters: %s', urls[i], str(regexps))
                    del(urls[i])
        numlinks=len(urls)
        log.info('Found %d links at %s.',numlinks, entry['url'])
        if numlinks>0:
            entry.setdefault('urls', urls)
            entry['url']=urls[0]
        else:
            raise UrlRewritingError('No useable links found at %s' % entry['url'])

@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteRmz, 'rmz', interfaces=['urlrewriter', 'task'], api_ver=2)