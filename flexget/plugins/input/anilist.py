from datetime import datetime

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
    """ " Creates entries for series and movies from your AniList list

    Syntax:
    anilist:
      username: <string>
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
      list:
        - <string>
        - <string>
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
                    'list': one_or_more({'type': 'string'}),
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
        selected_list_status = config.get('status', ['current', 'planning'])
        selected_release_status = config.get('release_status', ['all'])
        selected_formats = config.get('format', ['all'])
        selected_list_name = config.get('list', [])

        if not isinstance(selected_list_status, list):
            selected_list_status = [selected_list_status]

        if not isinstance(selected_release_status, list):
            selected_release_status = [selected_release_status]

        if not isinstance(selected_formats, list):
            selected_formats = [selected_formats]

        if not isinstance(selected_list_name, list):
            selected_list_name = [selected_list_name]
        selected_list_name = [i.lower() for i in selected_list_name]

        logger.debug(f'Selected List Status: {selected_list_status}')
        logger.debug(f'Selected Release Status: {selected_release_status}')
        logger.debug(f'Selected Formats: {selected_formats}')

        req_variables = {'user': config['username']}
        req_chunk = 1
        req_fields = (
            'id, status, title{ romaji, english }, synonyms, siteUrl, idMal, format, episodes, '
            'trailer{ site, id }, coverImage{ large }, bannerImage, genres, tags{ name }, '
            'externalLinks{ site, url }, startDate{ year, month, day }, endDate{ year, month, day}'
        )
        while req_chunk:
            req_query = (
                f'query ($user: String){{ collection: MediaListCollection(userName: $user, '
                f'type: ANIME, perChunk: 500, chunk: {req_chunk}, status_in: '
                f'[{", ".join([s.upper() for s in selected_list_status])}]) {{ hasNextChunk, '
                f'statuses: lists{{ status, name, list: entries{{ anime: media{{ {req_fields}'
                f' }}}}}}}}}}'
            )

            try:
                list_response = task.requests.post(
                    'https://graphql.anilist.co',
                    json={'query': req_query, 'variables': req_variables},
                )
                list_response = list_response.json()['data']
            except RequestException as e:
                logger.error(f'Error reading list: {e}')
                break
            except ValueError as e:
                logger.error(f'Invalid JSON response: {e}')
                break

            logger.trace(f'JSON output: {list_response}')
            for list_status in list_response.get('collection', {}).get('statuses', []):
                if selected_list_name and (
                    list_status.get('name')
                    and list_status.get('name').lower() not in selected_list_name
                ):
                    continue
                for anime in list_status['list']:
                    anime = anime.get('anime')
                    has_selected_release_status = (
                        anime.get('status')
                        and anime.get('status').lower() in selected_release_status
                    ) or 'all' in selected_release_status
                    has_selected_type = (
                        anime.get('format') and anime.get('format').lower() in selected_formats
                    ) or 'all' in selected_formats

                    if has_selected_type and has_selected_release_status:
                        ids = {}
                        try:
                            ids = task.requests.post(
                                'https://relations.yuna.moe/api/ids',
                                json={'anilist': anime.get('id')},
                            ).json()
                            logger.debug(f'Additional IDs: {ids}')
                        except RequestException as e:
                            logger.verbose(f'Couldn\'t fetch additional IDs: {e}')
                        if not isinstance(ids, dict):
                            ids = {}

                        logger.debug(f'Anime Entry: {anime}')
                        entry = Entry()
                        entry['al_id'] = anime.get('id', ids.get('anilist'))
                        entry['anidb_id'] = ids.get('anidb')
                        entry['kitsu_id'] = ids.get('kitsu')
                        entry['mal_id'] = anime.get('idMal', ids.get('myanimelist'))
                        entry['al_banner'] = anime.get('bannerImage')
                        entry['al_cover'] = anime.get('coverImage', {}).get('large')
                        entry['al_date_end'] = (
                            datetime(
                                year=anime.get('endDate').get('year'),
                                month=(anime.get('endDate').get('month') or 1),
                                day=(anime.get('endDate').get('day') or 1),
                            )
                            if anime.get('endDate').get('year')
                            else None
                        )
                        entry['al_date_start'] = (
                            datetime(
                                year=anime.get('startDate').get('year'),
                                month=(anime.get('startDate').get('month') or 1),
                                day=(anime.get('startDate').get('day') or 1),
                            )
                            if anime.get('startDate').get('year')
                            else None
                        )
                        entry['al_episodes'] = anime.get('episodes')
                        entry['al_format'] = anime.get('format')
                        entry['al_genres'] = anime.get('genres')
                        entry['al_links'] = {
                            item['site']: item['url'] for item in anime.get('externalLinks')
                        }
                        entry['al_list'] = list_status.get('name')
                        entry['al_list_status'] = (
                            list_status['status'].capitalize()
                            if list_status.get('status')
                            else None
                        )
                        entry['al_release_status'] = (
                            anime['status'].capitalize() if anime.get('status') else None
                        )
                        entry['al_tags'] = [t.get('name') for t in anime.get('tags')]
                        entry['al_title'] = anime.get('title')
                        entry['al_trailer'] = (
                            TRAILER_SOURCE[anime.get('trailer', {}).get('site')]
                            + anime.get('trailer', {}).get('id')
                            if anime.get('trailer')
                            and anime.get('trailer').get('site') in TRAILER_SOURCE
                            else None
                        )
                        entry['alternate_name'] = anime.get('synonyms', [])
                        eng_title = anime.get('title', {}).get('english')
                        if (
                            eng_title
                            and eng_title.lower() != anime.get('title', {}).get('romaji').lower()
                            and eng_title not in entry['alternate_name']
                        ):
                            entry['alternate_name'].insert(0, eng_title)
                        entry['series_name'] = entry['al_title'].get('romaji') or entry[
                            'al_title'
                        ].get('english')
                        entry['title'] = entry['series_name']
                        entry['url'] = anime.get('siteUrl')
                        if entry.isvalid():
                            yield entry
            req_chunk = req_chunk + 1 if list_response['collection']['hasNextChunk'] else False


@event('plugin.register')
def register_plugin():
    plugin.register(AniList, 'anilist', api_ver=2)
