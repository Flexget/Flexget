import re

from dateutil.parser import parse as dateutil_parse
from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException, TimedLimiter
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='awesomehd')


class SearchAwesomeHD:
    """
    AwesomeHD search plugin.
    """

    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'passkey': {'type': 'string'},
                    'only_internal': {'type': 'boolean', 'default': False},
                },
                'required': ['passkey'],
                'additionalProperties': False,
            },
            {'type': 'string'},
        ]
    }

    base_url = 'https://awesome-hd.me/'

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'passkey': config, 'only_internal': False}

        return config

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
        Search for entries on AwesomeHD
        """
        # need lxml to parse xml
        try:
            import lxml  # noqa
        except ImportError as e:
            logger.debug('Error importing lxml: {}', e)
            raise plugin.DependencyError(
                'awesomehd', 'lxml', 'lxml module required. ImportError: %s' % e
            )

        config = self.prepare_config(config)

        # set a domain limit, but allow the user to overwrite it
        if 'awesome-hd.me' not in task.requests.domain_limiters:
            task.requests.add_domain_limiter(TimedLimiter('awesome-hd.me', '5 seconds'))

        entries = set()

        # Can only search for imdb
        if not entry.get('imdb_id'):
            logger.debug('Skipping entry {} because of missing imdb id', entry['title'])
            return entries

        # Standard search params
        params = {
            'passkey': config['passkey'],
            'internal': int(config['only_internal']),
            'action': 'imdbsearch',
            'imdb': entry['imdb_id'],
        }

        try:
            response = task.requests.get(self.base_url + 'searchapi.php', params=params).content

        except RequestException as e:
            logger.error('Failed to search for imdb id {}: {}', entry['imdb_id'], e)
            return entries

        try:
            soup = get_soup(response, 'xml')
            if soup.find('error'):
                logger.error(soup.find('error').get_text())
                return entries
        except Exception as e:
            logger.error('Failed to parse xml result for imdb id {}: {}', entry['imdb_id'], e)
            return entries

        authkey = soup.find('authkey').get_text()

        for result in soup.find_all('torrent'):
            # skip audio releases for now
            if not result.find('resolution').get_text():
                logger.debug('Skipping audio release')
                continue

            e = Entry()

            e['imdb_id'] = result.find('imdb').get_text()
            e['torrent_id'] = int(result.find('id').get_text())
            e['uploaded_at'] = dateutil_parse(result.find('time').get_text())
            e['content_size'] = parse_filesize('{} b'.format(result.find('size').get_text()))
            e['torrent_snatches'] = int(result.find('snatched').get_text())
            e['torrent_seeds'] = int(result.find('seeders').get_text())
            e['torrent_leeches'] = int(result.find('leechers').get_text())
            e['release_group'] = result.find('releasegroup').get_text()
            e['freeleech_percent'] = int((1 - float(result.find('freeleech').get_text())) * 100)
            e['encode_status'] = result.find('encodestatus').get_text()
            e['subtitles'] = result.find('subtitles').get_text().split(', ')

            e['url'] = (
                self.base_url
                + 'torrents.php?action=download&id={}&authkey={}&torrent_pass={}'.format(
                    e['torrent_id'], authkey, config['passkey']
                )
            )

            # Generate a somewhat sensible title
            audio = result.find('audioformat').get_text().replace('AC-3', 'AC3')  # normalize a bit
            source = result.find('media').get_text()
            encoder = result.find('encoding').get_text()
            # calling a WEB-DL a remux is pretty redundant
            if 'WEB' in source.upper():
                encoder = re.sub('REMUX', '', encoder, flags=re.IGNORECASE).strip()

            e[
                'title'
            ] = '{movie_name} {year} {resolution} {source} {audio} {encoder}-{release_group}'.format(
                movie_name=result.find('name').get_text(),
                year=result.find('year').get_text(),
                resolution=result.find('resolution').get_text(),
                source=source,
                audio=audio,
                encoder=encoder,
                release_group=e['release_group'],
            )

            entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchAwesomeHD, 'awesomehd', interfaces=['search'], api_ver=2)
