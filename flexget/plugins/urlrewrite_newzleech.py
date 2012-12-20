from __future__ import unicode_literals, division, absolute_import
import urllib
import urllib2
import logging
import re
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet
from flexget.utils.soup import get_soup
from flexget.utils.tools import urlopener

log = logging.getLogger("newzleech")


class UrlRewriteNewzleech(object):
    """
        UrlRewriter or search by using newzleech.com
        TODO: implement basic url rewriting
    """

    # Search API
    @internet(log)
    def search(self, query, comparator, config=None):
        # TODO: Implement comparator matching
        url = u'http://newzleech.com/?%s' % str(urllib.urlencode({'q': query.encode('latin1'),
                                                                  'm': 'search', 'group': '', 'min': 'min',
                                                                  'max': 'max', 'age': '', 'minage': '', 'adv': ''}))
        #log.debug('Search url: %s' % url)

        txheaders = {
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Keep-Alive': '300',
            'Connection': 'keep-alive',
        }

        req = urllib2.Request(url, headers=txheaders)
        page = urlopener(req, log)

        soup = get_soup(page)

        nzbs = []

        for item in soup.find_all('table', attrs={'class': 'contentt'}):
            subject_tag = item.find('td', attrs={'class': 'subject'}).next
            subject = ''.join(subject_tag.find_all(text=True))
            complete = item.find('td', attrs={'class': 'complete'}).contents[0]
            size = item.find('td', attrs={'class': 'size'}).contents[0]
            nzb_url = 'http://newzleech.com/' + item.find('td', attrs={'class': 'get'}).next.get('href')

            #TODO: confidence match
            # generate regexp from entry title and see if it matches subject
            regexp = query
            wildcardize = [' ', '-']
            for wild in wildcardize:
                regexp = regexp.replace(wild, '.')
            regexp = '.*' + regexp + '.*'
            #log.debug('Title regexp: %s' % regexp)

            if re.match(regexp, subject):
                log.debug('%s matches to regexp' % subject)
                if complete != u'100':
                    log.debug('Match is incomplete %s from newzleech, skipping ..' % query)
                    continue
                log.info('Found \'%s\'' % query)

                def parse_size(value):
                    try:
                        num = float(value[:-3])
                    except:
                        log.error('Failed to parse_size %s' % value)
                        return 0
                    # convert into megabytes
                    if 'GB' in value:
                        num *= 1024
                    if 'KB' in value:
                        num /= 1024
                    return num

                nzb = Entry(title=subject, url=nzb_url, content_size=parse_size(size))
                nzb['url'] = nzb_url
                nzb['size'] = parse_size(size)

                nzbs.append(nzb)

        if not nzbs:
            log.debug('Unable to find %s' % query)
            return

        # choose largest file
        nzbs.sort(reverse=True, key=lambda x: x.get('content_size', 0))

        return nzbs

register_plugin(UrlRewriteNewzleech, 'newzleech', groups=['search'])
