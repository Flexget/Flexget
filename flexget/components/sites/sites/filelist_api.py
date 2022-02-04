from http import HTTPStatus

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.requests import Session as RequestSession

logger = logger.bind(name='filelist')
requests = RequestSession()


class SearchFileList:
    """
    FileList search plugin w/ API w00t.
    """

    api_url = 'https://filelist.io/api.php'

    valid_categories = {
        'Anime': '24',
        'Audio': '11',
        'Desene': '15',
        'Diverse': '18',
        'Docs': '16',
        'FLAC': '5',
        'Filme 3D': '25',
        'Filme 4K': '6',
        'Filme 4K Blu-Ray': '26',
        'Filme Blu-Ray': '20',
        'Filme DVD': '2',
        'Filme DVD-RO': '3',
        'Filme HD': '4',
        'Filme HD-RO': '19',
        'Filme SD': '1',
        'Jocuri Console': '10',
        'Jocuri PC': '9',
        'Linux': '17',
        'Mobile': '22',
        'Programe': '8',
        'Seriale 4K': '27',
        'Seriale HD': '21',
        'Seriale SD': '23',
        'Sport': '13',
        'TV': '14',
        'Videoclip': '12',
        'XXX': '7',
    }

    valid_extras = ['internal', 'moderated', 'freeleech', 'doubleup']

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'passkey': {'type': 'string'},
            'category': one_or_more({'type': 'string', 'enum': list(valid_categories.keys())}),
            'internal': {'type': 'boolean', 'default': False},
            'moderated': {'type': 'boolean', 'default': False},
            'freeleech': {'type': 'boolean', 'default': False},
            'doubleup': {'type': 'boolean', 'default': False},
        },
        'required': ['username', 'passkey'],
        'additionalProperties': False,
    }

    def get(self, url, params):

        try:
            response = requests.get(url, params=params, raise_status=False)
        except RequestException as e:
            raise plugin.PluginError(f'FileList request failed badly! {e}')

        if not response.ok:
            http_status = HTTPStatus(response.status_code)
            error_message = response.json().get('error', http_status.description)

            raise plugin.PluginError(
                f'FileList request failed; err code: {http_status}; err msg: `{error_message}`'
            )

        return response

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
        Search for entries on FileList
        """
        entries = []

        # mandatory params
        params = {
            'username': config['username'],
            'passkey': config['passkey'],
            'action': 'search-torrents',
        }

        # category
        if config.get('category'):
            params['category'] = (
                ','.join(self.valid_categories[cat] for cat in config['category'])
                if isinstance(config.get('category'), list)
                else self.valid_categories[config.get('category')]
            )

        # extras: internal release, moderated torrent, freeleech
        params.update({extra: 1 for extra in self.valid_extras if config.get(extra)})

        # set season/episode if series
        if entry.get('series_episode'):
            params['episode'] = entry.get('series_episode')
        if entry.get('series_season'):
            params['season'] = entry.get('series_season')

        for search_title in entry.get('search_strings', [entry.get('title')]):

            if entry.get('imdb_id'):
                params['type'] = 'imdb'
                params['query'] = entry.get('imdb_id')
                params['name'] = search_title
            else:
                params['type'] = 'name'
                params['query'] = search_title

            # get them results
            try:
                response = self.get(self.api_url, params)
            except RequestException as e:
                raise plugin.PluginError(f'FileList request failed badly! {e}')

            results = response.json()
            if not results:
                logger.verbose('No torrent found on Filelist for `{}`', search_title)
            else:
                logger.verbose(
                    '{} torrent(s) were found on Filelist for `{}`', len(results), search_title
                )

            for result in results:
                entry = Entry()

                entry['title'] = result['name']
                entry['url'] = result['download_link']
                entry['imdb'] = result['imdb']
                # size is returned in bytes but expected in MiB
                entry['content_size'] = result['size'] / 2**20
                entry['torrent_snatches'] = result['times_completed']
                entry['torrent_seeds'] = result['seeders']
                entry['torrent_leeches'] = result['leechers']
                entry['torrent_internal'] = bool(result['internal'])
                entry['torrent_moderated'] = bool(result['moderated'])
                entry['torrent_freeleech'] = bool(result['freeleech'])
                entry['torrent_genres'] = [
                    genres.strip() for genres in result['small_description'].split(',')
                ]

                entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchFileList, 'filelist_api', interfaces=['search'], api_ver=2)
