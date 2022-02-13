import re

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.soup import get_soup

logger = logger.bind(name='magnetdl')


class MagnetDL:
    """Creates entries from magnetdl categories"""

    url = 'https://www.magnetdl.com'

    schema = {
        'type': 'object',
        'properties': {
            'category': {
                'type': 'string',
                'enum': ['software', 'movies', 'games', 'e-books', 'tv', 'music'],
            },
        },
        'additionalProperties': False,
    }

    def _url(self, config):
        return self.url + '/download/' + config['category'] + '/'

    @cached('magnetdl', persist='12 minutes')
    def on_task_input(self, task, config):
        try:
            import cloudscraper
        except ImportError as e:
            logger.debug('Error importing cloudscraper: {}', e)
            raise plugin.DependencyError(
                issued_by='cfscraper', 
                missing='cloudscraper', 
                message='CLOudscraper module required. ImportError: %s' % e
            )

        scraper = cloudscraper.create_scraper()
        try:
            page = scraper.get(self._url(config))
        except RequestException as e:
            raise plugin.PluginError(str(e))
        if page.status_code != 200:
            raise plugin.PluginError('HTTP Request failed')

        soup = get_soup(page.text)
        soup_table = soup.find('table', class_='download').find('tbody')

        trs = soup_table.find_all('tr')
        if not trs:
            logger.verbose('Empty result')
            return
        for tr in trs:
            logger.debug(f'Parsing {tr}')
            try:
                magnet_td = tr.find('td', class_='m')
                if not magnet_td:
                    # skip empty trs
                    continue
                magnet_a = magnet_td.find('a')
                magnet = magnet_a['href']
                title_td = tr.find('td', class_='n')
                title_a = title_td.find('a')
                title = title_a['title']
                seed = int(tr.find('td', class_='s').text)
                leech = int(tr.find('td', class_='l').text)
                yield Entry(url=magnet, title=title, torrent_seeds=seed, torrent_leech=leech)
            except AttributeError:
                logger.warning('Parsing error occured')


@event('plugin.register')
def register_plugin():
    plugin.register(MagnetDL, 'magnetdl', api_ver=2, interfaces=['task'])
