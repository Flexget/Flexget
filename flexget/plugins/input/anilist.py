from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

log = logging.getLogger('anilist')

LIST_STATUS = ['current', 'planning', 'completed', 'dropped', 'paused', 'repeating']

RELEASE_STATUS = ['finished', 'releasing', 'not_yet_released', 'cancelled', 'all']

ANIME_FORMAT = ['tv', 'tv_short', 'movie', 'special', 'ova', 'ona', 'all']

TRAILER_SOURCE = {
    'youtube': 'https://www.youtube.com/embed/',
    'dailymotion': 'https://www.dailymotion.com/embed/video/'
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
                    'title_only': {'type': 'boolean'}
                },
                'required': ['username'],
                'additionalProperties': False,
            },
        ]
    }

    @cached('anilist', persist='2 hours')
    def on_task_input(self, task, config):
        entries = []
        if isinstance(config, str):
            config = {'username': config}
        selected_list_status = config['status'] if 'status' in config else ['current', 'planning']
        selected_release_status = config['release_status'] if 'release_status' in config else ['all']
        selected_formats = config['format'] if 'format' in config else ['all']
        lightweight = config['title_only'] if 'title_only' in config else False

        if not isinstance(selected_list_status, list):
            selected_list_status = [selected_list_status]

        if not isinstance(selected_release_status, list):
            selected_release_status = [selected_release_status]

        if not isinstance(selected_formats, list):
            selected_formats = [selected_formats]

        log.debug('selected_list_status: %s' % selected_list_status)
        log.debug('selected_release_status: %s' % selected_release_status)
        log.debug('selected_formats: %s' % selected_formats)

        list_json = []
        req_variables = {'user': config['username']}
        req_chunk = 1
        while req_chunk:
            req_query = ('query ($user: String){collection: MediaListCollection(userName: $user, type: ANIME, '
                        'perChunk: 500, chunk: %s, status_in: [%s]){ hasNextChunk, statuses: lists { list: entries { '
                        'anime: media { status, title{ romaji, english }, synonyms, siteUrl, idMal, format, episodes, '
                        'trailer{ site, id }, coverImage{ large }, bannerImage, genres, tags{ name }, externalLinks{ '
                        'site, url }}}}}}' % (req_chunk, ', '.join([s.upper() for s in selected_list_status])))

            try:
                list_response = task.requests.post(
                    'https://graphql.anilist.co', json={'query': req_query, 'variables': req_variables}
                )
            except RequestException as e:
                raise plugin.PluginError('Error reading list - {url}'.format(url=e))

            try:
                list_response = list_response.json()['data']
                list_json.append(list_response)
            except ValueError:
                raise plugin.PluginError('Invalid JSON response')
            req_chunk = req_chunk + 1 if list_response['collection']['hasNextChunk'] else False

        log.debug('JSON output: %s' % list_json)
        for list_index in list_json:
            for list_status in list_index['collection']['statuses']:
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
                        entries.append( Entry(title = anime['title']['romaji']) if lightweight else Entry(
                                title = anime['title']['romaji'],
                                alternate_name = [anime['title']['english']] + anime['synonyms'],
                                url = anime['siteUrl'],
                                al_release_status = anime['status'].capitalize(),
                                al_list_status = list_status,
                                al_idMal = anime['idMal'],
                                al_format = anime['format'],
                                al_episodes = anime['episodes'],
                                al_trailer = (TRAILER_SOURCE[anime['trailer']['site']]
                                    + anime['trailer']['id'] if anime['trailer'] else ''),
                                al_cover = anime['coverImage']['large'],
                                al_banner = anime['bannerImage'],
                                al_genres = anime['genres'],
                                al_tags = [t['name'] for t in anime['tags']],
                                al_title = anime['title'],
                                al_links = anime['externalLinks']
                            )
                        )
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(AniList, 'anilist', api_ver=2)
