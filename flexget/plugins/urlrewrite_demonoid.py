import re
import urllib
import logging
from plugin_urlrewriting import UrlRewritingError
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet, PluginWarning
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, StringComparator

log = logging.getLogger('demonoid')


class UrlRewriteDemonoid:
    """
    UrlRewriter and Search functionality for demonoid.

    Will accept:
      demonoid: <category>

    Or:
      demonoid:
        - category: <category>
        - quality: <quality>
        - sub-category: <category>

    Categories:

    * all
    * applications
    * audio books
    * tv
    * games
    * books
    * comics
    * anime
    * misc
    * movies
    * music
    * music videos
    * pictures
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('choice')
        root.accept_choices(['all', 'applications', 'audio books', 'tv', 'games', 'books', 'comics', 'anime', 'misc',
                             'movies', 'music', 'music videos', 'pictures'])
        #root = validator.factory()
        #root.accept('url')
        #advanced = root.accept('dict')
        #advanced.accept('url', key='url')
        return root

    def url_rewritable(self, feed, entry):
        return entry['url'].startswith('http://www.demonoid.me/files/details/')

    def url_rewrite(self, feed, entry):
        entry['url'] = entry['url'].replace('details', 'download')

    # search API
    @internet(log)
    def search(self, query, comparator, config):
        """
        """

        #TODO: check if urls are ever passed and if is wanted behaviour.
        #did: removed the url function & replaced it with category specification.

        #TODO: check wether we should support quality selection for movies/tv
        comparator.set_seq1(query)
        name = comparator.search_string()
        optiondict = ({'all': 0, 'applications': 5, 'audio books': 17, 'books': 11, 'comics': 10, 'games': 4,
                           'anime': 9, 'misc': 6, 'movies': 1, 'music': 2, 'music videos': 13, 'pictures': 8, 'tv': 3})

        url = ('http://www.demonoid.me/files/?category=%s&subcategory=All&quality=All&seeded=0&external=2&to=1&uid=0&query=%s'
              % (optiondict[config], urllib.quote(name.encode('utf-8'))))
        log.debug('Using %s as demonoid search url' % url)

        #url = url + urllib.quote(name.encode('utf-8'))
        page = urlopener(url, log)
        soup = get_soup(page)
        entries = []
        for td in soup.findAll('td', attrs={'colspan': '9'}):
            link = td.findAll('a')[0]
            found_title = link.contents[0]
            comparator.set_seq2(found_title)
            log.debug('name: %s' % comparator.a)
            log.debug('found name: %s' % comparator.b)
            log.debug('confidence: %s' % comparator.ratio())
            if not comparator.matches():
                continue

            entry = Entry()
            entry['title'] = found_title
            entry['url'] = 'http://www.demonoid.me' + link.get('href')
            tds = td.parent.nextSibling.nextSibling.findAll('td')
            entry['torrent_seeds'] = int(tds[6].findNext('font').contents[0])
            entry['torrent_leeches'] = int(tds[7].findNext('font').contents[0])
            entry['search_ratio'] = comparator.ratio()
            entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
            # Parse content_size
            size = tds[3].contents[0]
            size = re.search(r'([\.\d]+) ([GMK])B', size)
            if size:
                if size.group(2) == 'G':
                    entry['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                elif size.group(2) == 'M':
                    entry['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                else:
                    entry['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)

            entries.append(entry)

        if not entries:
            dashindex = name.rfind('-')
            if dashindex != -1:
                return self.search_title(name[:dashindex], comparator=comparator, config=config)
            else:
                raise PluginWarning('No close matches for %s' % name, log, log_once=True)

        log.debug('search got %d results' % len(entries))

        #TODO: check of this does anything/should even be here. indent seems strange.
        def score(a):
            return torrent_availability(a['torrent_seeds'], a['torrent_leeches'])

        entries.sort(reverse=True, key=lambda x: x.get('search_sorted'))
        return entries

register_plugin(UrlRewriteDemonoid, 'demonoid', groups=['urlrewriter', 'search'])
