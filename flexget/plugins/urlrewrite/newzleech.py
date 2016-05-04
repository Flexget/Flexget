from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode

import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup

log = logging.getLogger("newzleech")


class UrlRewriteNewzleech(object):
    """
        UrlRewriter or search by using newzleech.com
        TODO: implement basic url rewriting
    """

    # Search API
    @plugin.internet(log)
    def search(self, task, entry, config=None):

        txheaders = {
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Keep-Alive': '300',
            'Connection': 'keep-alive',
        }
        nzbs = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = entry['title']
            url = u'http://newzleech.com/?%s' % str(urlencode({'q': query.encode('latin1'),
                                                                      'm': 'search', 'group': '', 'min': 'min',
                                                                      'max': 'max', 'age': '', 'minage': '',
                                                                      'adv': ''}))
            # log.debug('Search url: %s' % url)

            page = task.requests.get(url, headers=txheaders)
            soup = get_soup(page.text)

            for item in soup.find_all('table', attrs={'class': 'contentt'}):
                subject_tag = item.find('td', attrs={'class': 'subject'}).__next__
                subject = ''.join(subject_tag.find_all(text=True))
                complete = item.find('td', attrs={'class': 'complete'}).contents[0]
                size = item.find('td', attrs={'class': 'size'}).contents[0]
                nzb_url = 'http://newzleech.com/' + item.find('td', attrs={'class': 'get'}).next.get('href')

                # generate regexp from entry title and see if it matches subject
                regexp = query
                wildcardize = [' ', '-']
                for wild in wildcardize:
                    regexp = regexp.replace(wild, '.')
                regexp = '.*' + regexp + '.*'
                # log.debug('Title regexp: %s' % regexp)

                if re.match(regexp, subject):
                    log.debug('%s matches to regexp' % subject)
                    if complete != u'100':
                        log.debug('Match is incomplete %s from newzleech, skipping ..' % query)
                        continue
                    log.info('Found \'%s\'' % query)

                    try:
                        size_num = float(size[:-3])
                    except (ValueError, TypeError):
                        log.error('Failed to parse_size %s' % size)
                        size_num = 0
                    # convert into megabytes
                    if 'GB' in size:
                        size_num *= 1024
                    if 'KB' in size:
                        size_num /= 1024

                    # choose largest file
                    nzbs.add(Entry(title=subject, url=nzb_url, content_size=size_num, search_sort=size_num))

        return nzbs


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNewzleech, 'newzleech', groups=['search'], api_ver=2)
