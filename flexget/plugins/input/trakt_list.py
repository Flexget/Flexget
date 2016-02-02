from __future__ import unicode_literals, division, absolute_import
import logging
import re

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.plugins.api_trakt import get_api_url, get_session, make_list_slug

log = logging.getLogger('trakt_list')


field_maps = {
    'movie': {
        'title': lambda i: '%s (%s)' % (i['movie']['title'], i['movie']['year']),
        'movie_name': 'movie.title',
        'movie_year': 'movie.year',
        'imdb_id': 'movie.ids.imdb',
        'tmdb_id': 'movie.ids.tmdb',
        'trakt_movie_id': 'movie.ids.trakt',
        'trakt_movie_slug': 'movie.ids.slug'
    },
    'show': {
        'title': lambda i: '%s (%s)' % (i['show']['title'], i['show']['year']),
        'series_name': lambda i: '%s (%s)' % (i['show']['title'], i['show']['year']),
        'imdb_id': 'show.ids.imdb',
        'tvdb_id': 'show.ids.tvdb',
        'tvrage_id': 'show.ids.tvrage',
        'tmdb_id': 'show.ids.tmdb',
        'trakt_show_id': 'show.ids.trakt',
        'trakt_slug': 'show.ids.slug'
    },
    'episode': {
        'title': lambda i: ('%s (%s) S%02dE%02d %s' % (i['show']['title'], i['show']['year'], i['episode']['season'],
                                                       i['episode']['number'], i['episode']['title'] or '')).strip(),
        'series_name': lambda i: '%s (%s)' % (i['show']['title'], i['show']['year']),
        'series_season': 'episode.season',
        'series_episode': 'episode.number',
        'series_id': lambda i: 'S%02dE%02d' % (i['episode']['season'], i['episode']['number']),
        'imdb_id': 'show.ids.imdb',
        'tvdb_id': 'show.ids.tvdb',
        'tvrage_id': 'show.ids.tvrage',
        'trakt_episode_id': 'episode.ids.trakt',
        'trakt_show_id': 'show.ids.trakt',
        'trakt_show_slug': 'show.ids.slug',
        'trakt_ep_name': 'episode.title'
    }
}


class TraktList(object):
    """Creates an entry for each item in your trakt list.

    Syntax:

    trakt_list:
      username: <value>
      type: <shows|movies|episodes>
      list: <collection|watchlist|watched|ratings|rating:<1|2|3|4|5|6|7|8|9|10>|custom list name>
      strip_dates: <yes|no>

    Options username, type and list are required.
    """

    schema = {
        'type': 'object',
        'properties': {
            'account': {'type': 'string'},
            'username': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['shows', 'movies', 'episodes']},
            'list': {"oneOf": [
              {'type': 'string'}, 
              {
                  "type": "object",
                  "properties": {
                      "rating": {"type": "integer", 'enum': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}
                  },
                  "additionalProperties": False
            }]},
            'strip_dates': {'type': 'boolean', 'default': False}
        },
        'required': ['type', 'list'],
        'anyOf': [{'required': ['username']}, {'required': ['account']}],
        'error_anyOf': 'At least one of `username` or `account` options are needed.',
        'additionalProperties': False,
        'not': {
            'properties': {
                'type': {'enum': ['episodes']},
                'list': {'enum': ['collection', 'watched']}
            }
        },
        'error_not': '`collection` and `watched` lists do not support `episodes` type'
    }

    @cached('trakt_list', persist='2 hours')
    def on_task_input(self, task, config):
        if config.get('account') and not config.get('username'):
            config['username'] = 'me'
        session = get_session(account=config.get('account'))
        endpoint = ['users', config['username']]
        if type(config['list']) is dict:
            endpoint += ('ratings', config['type'], config['list']['rating'])
        elif config['list'] in ['collection', 'watchlist', 'watched', 'ratings']:
            endpoint += (config['list'], config['type'])
        else:
            endpoint += ('lists', make_list_slug(config['list']), 'items')

        log.verbose('Retrieving `%s` list `%s`' % (config['type'], config['list']))
        try:
            result = session.get(get_api_url(endpoint))
            try:
                data = result.json()
            except ValueError:
                log.debug('Could not decode json from response: %s', result.text)
                raise plugin.PluginError('Error getting list from trakt.')
        except RequestException as e:
            raise plugin.PluginError('Could not retrieve list from trakt (%s)' % e.args[0])

        if not data:
            log.warning('No data returned from trakt for %s list %s.' % (config['type'], config['list']))
            return

        entries = []
        list_type = (config['type']).rstrip('s')
        for item in data:
            # Collection and watched lists don't return 'type' along with the items (right now)
            if 'type' in item and item['type'] != list_type:
                log.debug('Skipping %s because it is not a %s' % (item[item['type']].get('title', 'unknown'),
                                                                  list_type))
                continue
            if list_type != 'episode' and not item[list_type]['title']:
                # Skip shows/movies with no title
                log.warning('Item in trakt list does not appear to have a title, skipping.')
                continue
            entry = Entry()
            if list_type == 'episode':
                entry['url'] = 'http://trakt.tv/shows/%s/seasons/%s/episodes/%s' % (
                    item['show']['ids']['slug'], item['episode']['season'], item['episode']['number'])
            else:
                entry['url'] = 'http://trakt.tv/%s/%s' % (list_type, item[list_type]['ids'].get('slug'))
            entry.update_using_map(field_maps[list_type], item)
            if entry.isvalid():
                if config.get('strip_dates'):
                    # Remove year from end of name if present
                    entry['title'] = re.sub(r'\s+\(\d{4}\)$', '', entry['title'])
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TraktList, 'trakt_list', api_ver=2)
