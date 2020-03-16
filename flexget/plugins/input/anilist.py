from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

logger = logger.bind(name='anilist')

LIST_STATUS = ['current', 'planning', 'completed', 'dropped', 'paused', 'repeating']

RELEASE_STATUS = ['finished', 'releasing', 'not_yet_released', 'cancelled', 'all']

ANIME_FORMAT = ['tv', 'tv_short', 'movie', 'special', 'ova', 'ona', 'all']

TRAILER_SOURCE = {
    'youtube': 'https://www.youtube.com/embed/',
    'dailymotion': 'https://www.dailymotion.com/embed/video/',
}


class AniList(object):
    """" Creates entries for series and movies from your AniList list

    Syntax:
    anilist:
      username: <value>
      status:
        - <current|planning|completed|dropped|paused|repeating>
        - <current|planning|completed|dropped|paused|repeating>
        ...
      release_status:
        - <all|finished|releasing|not_yet_released|cancelled>
        - <finished|releasing|not_yet_released|cancelled>
        ...
      format:
        - <all|tv|tv_short|movie|special|ova|ona>
        - <tv|tv_short|movie|special|ova|ona>
        ...
    """

    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'status': one_or_more(
                        {'type': 'string', 'enum': LIST_STATUS}, unique_items=True
                    ),
                    'release_status': one_or_more(
                        {'type': 'string', 'enum': RELEASE_STATUS}, unique_items=True
                    ),
                    'format': one_or_more(
                        {'type': 'string', 'enum': ANIME_FORMAT}, unique_items=True
                    ),
                },
                'required': ['username'],
                'additionalProperties': False,
            },
        ]
    }

    @cached('anilist', persist='2 hours')
    def on_task_input(self, task, config):
        if isinstance(config, str):
            config = {'username': config}
        selected_list_status = config['status'] if 'status' in config else ['current', 'planning']
        selected_release_status = (
            config['release_status'] if 'release_status' in config else ['all']
        )
        selected_formats = config['format'] if 'format' in config else ['all']

        if not isinstance(selected_list_status, list):
            selected_list_status = [selected_list_status]

        if not isinstance(selected_release_status, list):
            selected_release_status = [selected_release_status]

        if not isinstance(selected_formats, list):
            selected_formats = [selected_formats]

        logger.debug('Selected List Status: {}', selected_list_status)
        logger.debug('Selected Release Status: {}', selected_release_status)
        logger.debug('Selected Formats: {}', selected_formats)

        req_variables = {'user': config['username']}
        req_chunk = 1
        req_fields = (
            'status, title{ romaji, english }, synonyms, siteUrl, idMal, format, episodes, '
            'trailer{ site, id }, coverImage{ large }, bannerImage, genres, tags{ name }, '
            'externalLinks{ site, url }'
        )
        while req_chunk:
            req_query = (
                f'query ($user: String){{ collection: MediaListCollection(userName: $user, '
                f'type: ANIME, perChunk: 500, chunk: {req_chunk}, status_in: '
                f'[{", ".join([s.upper() for s in selected_list_status])}]) {{ hasNextChunk, '
                f'statuses: lists{{ status, list: entries{{ anime: media{{ {req_fields} }}}}}}}}}}'
            )

            try:
                list_response = task.requests.post(
                    'https://graphql.anilist.co',
                    json={'query': req_query, 'variables': req_variables},
                )
            except RequestException as e:
                raise plugin.PluginError('Error reading list - {url}'.format(url=e))

            try:
                list_response = list_response.json()['data']
                logger.debug('JSON output: {}', list_response)
                for list_status in list_response['collection']['statuses']:
                    for anime in list_status['list']:
                        anime = anime['anime']
                        has_selected_release_status = (
                            anime['status'].lower() in selected_release_status
                            or 'all' in selected_release_status
                        )
                        has_selected_type = (
                            anime['format'].lower() in selected_formats
                            or 'all' in selected_formats
                        )
                        if has_selected_type and has_selected_release_status:
                            entry = Entry()
                            entry['title'] = anime['title']['romaji']
                            entry['al_title'] = anime['title']
                            entry['al_format'] = anime['format']
                            entry['al_release_status'] = anime['status'].capitalize()
                            entry['al_list_status'] = list_status['status'].capitalize()
                            entry['alternate_name'] = anime.get('synonyms', [])
                            if (
                                anime['title'].get('english')
                                and anime['title'].get('english') != anime['title']['romaji']
                                and anime['title'].get('english') not in entry['alternate_name']
                            ):
                                entry['alternate_name'].insert(0, anime['title']['english'])
                            entry['url'] = anime['siteUrl']
                            entry['al_idMal'] = anime['idMal']
                            entry['al_episodes'] = anime['episodes']
                            entry['al_trailer'] = (
                                TRAILER_SOURCE[anime['trailer']['site']] + anime['trailer']['id']
                                if anime['trailer']
                                else ''
                            )
                            entry['al_cover'] = anime['coverImage']['large']
                            entry['al_banner'] = anime['bannerImage']
                            entry['al_genres'] = anime['genres']
                            entry['al_tags'] = [t['name'] for t in anime['tags']]
                            entry['al_links'] = anime['externalLinks']
                            if entry.isvalid():
                                yield entry
                req_chunk = req_chunk + 1 if list_response['collection']['hasNextChunk'] else False

            except ValueError:
                raise plugin.PluginError('Invalid JSON response')


@event('plugin.register')
def register_plugin():
    plugin.register(AniList, 'anilist', api_ver=2)
