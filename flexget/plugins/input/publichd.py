import urlparse
import logging
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached
from flexget.utils.tools import urlopener
from werkzeug.urls import url_quote

log = logging.getLogger('publichd')


class InputPublicHD(object):
    """
        Parses torrents from hdts.ru


        Configuration expects the URL of a search result:
        
        publichd: https://publichd.eu/index.php?page=torrents&category=14
        
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('url')
        return root

    @cached('publichd')
    @internet(log)
    def on_task_input(self, task, config):
        if isinstance(config, basestring):
            config = {'url': config}
        log.debug('InputPlugin publichd requesting url %s' % config['url'])
        page = urlopener(config['url'], log)
        soup = get_soup(page)
        log.debug('Detected encoding %s' % soup.originalEncoding)

        return self.create_entries(soup, config['url'])

    def create_entries(self, soup, baseurl):

        table = soup.find('table', id='torrbg')

        queue = []
        for tr in table.find_all('tr')[1:]:
            title = None
            url = None
            for link in tr.find_all('a'):
                href = link['href']
                if href.startswith('index.php?page=torrent-details'):
                    title = link.string
                    log.debug('Found title "%s"', title)
                elif href.startswith('magnet:'):
                    #url = urlparse.urljoin(baseurl, href)
                    url = href
                    log.debug('Found url "%s"', url)
            if title and url:
                entry = Entry(title = title, url = url)
                queue.append(entry)

        return queue
    
    @internet(log)
    def search(self, entry, config=None):
        if isinstance(config, basestring):
            config = {'url': config}
        config['url'] = '%s&search=%s' % (config['url'], url_quote(entry['title'], 'utf8'))
        log.debug('InputPlugin publichd requesting url %s' % config['url'])
        page = urlopener(config['url'], log)
        soup = get_soup(page)
        log.debug('Detected encoding %s' % soup.originalEncoding)

        return self.create_entries(soup, config['url'])
    
register_plugin(InputPublicHD, 'publichd', api_ver=2, groups=['search'])
