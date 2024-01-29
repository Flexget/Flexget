from dateutil.parser import parse as dateutil_parse
from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException, TimedLimiter
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='passthepopcorn')

TAGS = [
    'action',
    'adventure',
    'animation',
    'arthouse',
    'asian',
    'biography',
    'camp',
    'comedy',
    'crime',
    'cult',
    'documentary',
    'drama',
    'experimental',
    'exploitation',
    'family',
    'fantasy',
    'film.noir',
    'history',
    'horror',
    'martial.arts',
    'musical',
    'mystery',
    'performance',
    'philosophy',
    'politics',
    'romance',
    'sci.fi',
    'short',
    'silent',
    'sport',
    'thriller',
    'video.art',
    'war',
    'western',
]

ORDERING = {
    'Relevance': 'relevance',
    'Time added': 'timeadded',
    'Time w/o reseed': 'timenoreseed',
    'First time added': 'creationtime',
    'Year': 'year',
    'Title': 'title',
    'Size': 'size',
    'Snatched': 'snatched',
    'Seeders': 'seeders',
    'Leechers': 'leechers',
    'Runtime': 'runtime',
    'IMDb rating': 'imdb',
    'IMDb vote count': 'imdbvotes',
    'PTP rating': 'ptprating',
    'PTP vote count': 'ptpvotes',
    'MC rating': 'mc',
    'RT rating': 'rt',
    'Bookmark count': 'bookmarks',
}

RELEASE_TYPES = {'non-scene': 0, 'scene': 1, 'golden popcorn': 2}


class SearchPassThePopcorn:
    """
    PassThePopcorn search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'apiuser': {'type': 'string'},
            'apikey': {'type': 'string'},
            'passkey': {'type': 'string'},
            'tags': one_or_more({'type': 'string', 'enum': TAGS}, unique_items=True),
            'order_by': {'type': 'string', 'enum': list(ORDERING.keys()), 'default': 'Time added'},
            'order_desc': {'type': 'boolean', 'default': True},
            'freeleech': {'type': 'boolean'},
            'release_type': {'type': 'string', 'enum': list(RELEASE_TYPES.keys())},
            'grouping': {'type': 'boolean', 'default': False},
        },
        'required': ['apiuser', 'apikey', 'passkey'],
        'additionalProperties': False,
    }

    base_url = 'https://passthepopcorn.me/'
    errors = False

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
        Search for entries on PassThePopcorn
        """
        params = {}

        if 'tags' in config:
            tags = config['tags'] if isinstance(config['tags'], list) else [config['tags']]
            params['taglist'] = ',+'.join(tags)

        release_type = config.get('release_type')
        if release_type:
            params['scene'] = RELEASE_TYPES[release_type]

        if config.get('freeleech'):
            params['freetorrent'] = int(config['freeleech'])

        ordering = 'desc' if config['order_desc'] else 'asc'

        grouping = int(config['grouping'])

        entries = set()

        params.update(
            {
                'order_by': ORDERING[config['order_by']],
                'order_way': ordering,
                'action': 'advanced',
                'json': 'noredirect',
                'grouping': grouping,
            }
        )

        search_strings = entry.get('search_strings', [entry['title']])

        request_headers = {"ApiUser": config['apiuser'], "ApiKey": config['apikey']}

        # searching with imdb id is much more precise
        if entry.get('imdb_id'):
            search_strings = [entry['imdb_id']]
        else:
            # use the movie year if available to improve search results.
            if 'movie_year' in entry:
                # the movie list plugin seems to have garbage in the year entry sometimes like a 1 for the year
                # validate we have a useful year to filter on
                try:
                    if int(entry['movie_year']) > 1900:
                        params['year'] = int(entry['movie_year'])
                    else:
                        logger.error(
                            f"Searching for '{entry['title']}' ignoring invalid movie_year: '{entry['movie_year']}'"
                        )
                except ValueError:
                    logger.error(
                        f"Searching for '{entry['title']}'  ignoring non numeric movie_year: '{entry['movie_year']}'"
                    )

        task.requests.add_domain_limiter(
            TimedLimiter('passthepopcorn.me', '5 seconds'), replace=False
        )

        for search_string in search_strings:
            params['searchstr'] = search_string
            logger.debug('Using search params: {}', params)
            try:
                siteresponse = task.requests.get(
                    self.base_url + 'torrents.php', headers=request_headers, params=params
                )
                result = siteresponse.json()
                logger.debug('PTP Search Request: {}', str(siteresponse.url))
            except RequestException as e:
                raise plugin.PluginError('Error searching PassThePopcorn. %s' % str(e))

            total_results = result['TotalResults']
            logger.debug('Total Search results: {}', total_results)

            authkey = result['AuthKey']
            passkey = result['PassKey']

            for movie in result['Movies']:
                # skip movies with wrong year
                # don't consider if we have imdb_id (account for year discrepancies if we know we have
                # the right movie)
                if (
                    'imdb_id' not in movie
                    and 'movie_year' in movie
                    and int(movie['Year']) != int(entry['movie_year'])
                ):
                    logger.debug(
                        'Movie year {} does not match default {}',
                        movie['Year'],
                        entry['movie_year'],
                    )
                    continue

                # imdb id in the json result is without 'tt'
                if 'imdb_id' in movie and movie['ImdbId'] not in entry['imdb_id']:
                    logger.debug('imdb id {} does not match {}', movie['ImdbId'], entry['imdb_id'])
                    continue

                for torrent in movie['Torrents']:
                    e = Entry()

                    # Add the PTP qualities to the title so the quality plugin has a better chance
                    release_res = torrent['Resolution']
                    release_res = release_res.replace(
                        "PAL", "576p"
                    )  # Common PAL DVD vertial resolution
                    release_res = release_res.replace(
                        "NTSC", "480p"
                    )  # Common NTSC DVD vertial resolution
                    # many older releases have a resolution defined as 624x480 for example this will split the value at take the hight
                    tsplit = release_res.split("x", 1)
                    if len(tsplit) > 1:
                        release_res = tsplit[1] + 'p'

                    release_name = torrent['ReleaseName'].replace(
                        "4K", ""
                    )  # Remove 4K from release name as that is often the source not the torrent resolution it confuses the quality plugin
                    e['title'] = (
                        f"{release_name} [{release_res} {torrent['Source']} {torrent['Codec']} {torrent['Container']}]"
                    )

                    e['imdb_id'] = entry.get('imdb_id')

                    e['torrent_tags'] = movie['Tags']
                    e['content_size'] = parse_filesize(torrent['Size'] + ' b')
                    e['torrent_snatches'] = int(torrent['Snatched'])
                    e['torrent_seeds'] = int(torrent['Seeders'])
                    e['torrent_leeches'] = int(torrent['Leechers'])
                    e['torrent_id'] = int(torrent['Id'])
                    e['golden_popcorn'] = torrent['GoldenPopcorn']
                    e['checked'] = torrent['Checked']
                    e['scene'] = torrent['Scene']
                    e['uploaded_at'] = dateutil_parse(torrent['UploadTime'])

                    e['ptp_remaster_title'] = torrent.get(
                        'RemasterTitle'
                    )  # tags such as remux, 4k remaster, etc.
                    e['ptp_quality'] = torrent.get(
                        'Quality'
                    )  # high, ultra high, or standard definition
                    e['ptp_resolution'] = torrent.get('Resolution')  # 1080p, 720p, etc.
                    e['ptp_source'] = torrent.get('Source')  # blu-ray, dvd, etc.
                    e['ptp_container'] = torrent.get('Container')  # mkv, vob ifo, etc.
                    e['ptp_codec'] = torrent.get('Codec')  # x264, XviD, etc.

                    e['url'] = (
                        self.base_url
                        + 'torrents.php?action=download&id={}&authkey={}&torrent_pass={}'.format(
                            e['torrent_id'], authkey, passkey
                        )
                    )
                    logger.debug('Add Entry: {} Seeds:{}', e['title'], e['torrent_seeds'])
                    entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchPassThePopcorn, 'passthepopcorn', interfaces=['search'], api_ver=2)
