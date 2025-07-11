import time
from json import JSONDecodeError

import pendulum
from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry, register_lazy_lookup
from flexget.event import event
from flexget.utils import requests
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException, TokenBucketLimiter

logger = logger.bind(name='anilist')

LIST_STATUS = ['current', 'planning', 'completed', 'dropped', 'paused', 'repeating']

RELEASE_STATUS = ['finished', 'releasing', 'not_yet_released', 'cancelled', 'all']

ANIME_FORMAT = ['tv', 'tv_short', 'movie', 'special', 'ova', 'ona', 'all']

TRAILER_SOURCE = {
    'youtube': 'https://www.youtube.com/embed/',
    'dailymotion': 'https://www.dailymotion.com/embed/video/',
}

RELATIONS_MAP = {
    'anidb_id': 'anidb',
    'anime_planet_id': 'anime-planet',
    'anisearch_id': 'anisearch',
    'imdb_id': 'imdb',
    'kitsu_id': 'kitsu',
    'livechart_id': 'livechart',
    'mal_id': 'myanimelist',
    'notify_moe_id': 'notify-moe',
    'tmdb_id': 'themoviedb',
    'tvdb_id': 'thetvdb',
}


class AniList:
    """Creates entries for series and movies from your AniList list.

    Syntax::

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
        task.requests.add_domain_limiter(TokenBucketLimiter('anilist.co', 90, '1 minute'))
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

        logger.debug('Selected List Status: {}', selected_list_status)
        logger.debug('Selected Release Status: {}', selected_release_status)
        logger.debug('Selected Formats: {}', selected_formats)

        req_variables = {'user': config['username']}
        req_amount = min(task.config.get('limit', {}).get('amount', 500), 500)
        req_chunk = 1
        req_fields = (
            'id',
            'idMal',
            'title{ romaji, english, native }',
            'type',
            'format',
            'status',
            'description',
            'startDate{ year, month, day }',
            'endDate{ year, month, day}',
            'season',
            'seasonYear',
            'seasonInt',
            'episodes',
            'duration',
            'countryOfOrigin',
            'source',
            'hashtag',
            'trailer{ site, id, thumbnail }',
            'updatedAt',
            'coverImage{ extraLarge }',
            'bannerImage',
            'genres',
            'synonyms',
            'averageScore',
            'meanScore',
            'popularity',
            'trending',
            'favourites',
            'tags{ name }',
            # 'relations',
            # 'characters',
            # 'staff',
            'studios{ nodes{ name }}',
            'isAdult',
            'nextAiringEpisode{ airingAt, episode }',
            'airingSchedule{ nodes{ airingAt, episode }}',
            # 'trends',
            'externalLinks{ site, url }',
            'streamingEpisodes{ title, url, site }',
            'rankings{ context }',
            # 'recommendations',
            'stats{ scoreDistribution{ score, amount }, statusDistribution{ status, amount }}',
            'siteUrl',
            'modNotes',
        )
        while req_chunk:
            req_query = (
                f'query ($user: String){{ collection: MediaListCollection(userName: $user, '
                f'type: ANIME, perChunk: {req_amount}, chunk: {req_chunk}, status_in: '
                f'[{", ".join([s.upper() for s in selected_list_status])}]) {{ hasNextChunk, '
                f'statuses: lists{{ status, name, list: entries{{ anime: media{{ {", ".join(req_fields)}'
                f' }}}}}}}}}}'
            )

            try:
                list_response = task.requests.post(
                    'https://graphql.anilist.co',
                    json={'query': req_query, 'variables': req_variables},
                )
                list_response = list_response.json()['data']
            except RequestException as e:
                logger.error('Error reading list: {}', e)
                if hasattr(e.response, 'headers') and e.response.headers.get('Retry-After'):
                    wait = e.response.headers.get('Retry-After')
                    logger.warning('Rate-limited. Waiting {} seconds before retrying', wait)
                    time.sleep(float(wait))
                    continue
                break
            except ValueError as e:
                logger.error('Invalid JSON response: {}', e)
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
                        logger.debug('Anime Entry: {}', anime)
                        entry = Entry()
                        entry['al_id'] = anime.get('id')
                        if anime.get('idMal'):
                            entry['mal_id'] = anime['idMal']
                        entry['al_banner'] = anime.get('bannerImage')
                        entry['al_cover'] = anime.get('coverImage', {}).get('large')
                        entry['al_date_end'] = (
                            pendulum.date(
                                year=anime.get('endDate').get('year'),
                                month=(anime.get('endDate').get('month') or 1),
                                day=(anime.get('endDate').get('day') or 1),
                            )
                            if anime.get('endDate').get('year')
                            else None
                        )
                        entry['al_date_start'] = (
                            pendulum.date(
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
                        entry['al_season'] = f'{anime.get("seasonYear")} {anime.get("season")}'
                        entry['anilist'] = anime
                        entry['alternate_name'] = anime.get('synonyms', [])
                        eng_title = anime.get('title', {}).get('english')
                        if (
                            eng_title
                            and eng_title.lower() != anime.get('title', {}).get('romaji').lower()
                            and eng_title not in entry['alternate_name']
                        ):
                            entry['alternate_name'].insert(0, eng_title)
                        entry['series_name'] = (
                            entry['al_title'].get('romaji') or entry['al_title'].get('english')
                        ).strip()
                        entry['title'] = entry['series_name']
                        entry['url'] = anime.get('siteUrl')
                        entry.add_lazy_fields(relations_lookup, RELATIONS_MAP)
                        if entry.isvalid():
                            yield entry
            req_chunk = req_chunk + 1 if list_response['collection']['hasNextChunk'] else False


@register_lazy_lookup('relations_lookup')
def relations_lookup(entry: Entry):
    ids = {}
    try:
        ids: dict[str, str | int] = requests.post(
            'https://relations.yuna.moe/api/v2/ids',
            json={'anilist': entry.get('al_id', eval_lazy=False)},
        ).json()
        logger.debug('Additional IDs: {}', ids)
    except RequestException as e:
        logger.warning('Error fetching additional IDs: {}', e)
    except JSONDecodeError as e:
        logger.warning('Unexpected relations: {}', e)
        ids = {}
    entry.update_using_map(RELATIONS_MAP, ids, True)


@event('plugin.register')
def register_plugin():
    plugin.register(AniList, 'anilist', api_ver=2)
