import re

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='FTDB')


class UrlRewriteFTDB:
    """FTDB RSS url_rewrite"""

    def url_rewritable(self, task, entry):
        # url = entry['url']
        if re.match(r'^http://www\.frenchtorrentdb\.com/[^/]+(?!/)[^/]+&rss=1', entry['url']):
            return True
        return False

    def url_rewrite(self, task, entry):
        old_url = entry['url']
        page_url = old_url.replace('DOWNLOAD', 'INFOS')
        page_url = page_url.replace('&rss=1', '')

        new_url = self.parse_download_page(page_url, task.requests)
        logger.debug('PAGE URL NEEDED : {}', page_url)
        logger.debug('{} OLD is rewrited to NEW {}', old_url, new_url)
        entry['url'] = new_url

    def parse_download_page(self, page_url, requests):
        page = requests.get(page_url)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)
        tag_a = soup.find("a", {"class": "dl_link"})
        if not tag_a:
            if soup.findAll(text="Connexion ?"):
                raise UrlRewritingError(
                    'You are not logged in,\
                                         check if your cookie for\
                                         authentication is up to date'
                )
            else:
                raise UrlRewritingError(
                    'You have reached your download\
                                        limit per 24hours, so I cannot\
                                        get the torrent'
                )
        torrent_url = "http://www.frenchtorrentdb.com" + tag_a.get('href') + "&js=1"
        logger.debug('TORRENT URL is : {}', torrent_url)
        return torrent_url


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteFTDB, 'frenchtorrentdb', interfaces=['urlrewriter'], api_ver=2)
