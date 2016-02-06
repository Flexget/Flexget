from __future__ import unicode_literals, division, absolute_import
import logging
import re

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json
from flexget.plugins.api_trakt import get_api_url, get_entry_ids, get_session, make_list_slug


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

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'account': {'type': 'string'},
            'list': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['shows', 'seasons', 'episodes', 'movies', 'auto'], 'default': 'auto'}
        },
        'required': ['list'],
        'anyOf': [{'required': ['username']}, {'required': ['account']}],
        'error_anyOf': 'At least one of `username` or `account` options are needed.',
        'additionalProperties': False
    }

    @staticmethod
    def submit(config, entries, remove=False):
        """Submits movies or episodes to trakt api."""
        if config.get('account') and not config.get('username'):
            config['username'] = 'me'
        found = {}
        for entry in entries:
            if config['type'] in ['auto', 'shows', 'seasons', 'episodes'] and entry.get('series_name') is not None:
                show = {'title': entry['series_name'], 'ids': get_entry_ids(entry)}
                if config['type'] in ['auto', 'seasons', 'episodes'] and entry.get('series_season') is not None:
                    season = {'number': entry['series_season']}
                    if config['type'] in ['auto', 'episodes'] and entry.get('series_episode') is not None:
                        season['episodes'] = [{'number': entry['series_episode']}]
                    show['seasons'] = [season]
                if config['type'] in ['seasons', 'episodes'] and 'seasons' not in show:
                    log.debug('Not submitting `%s`, no season found.' % entry['title'])
                    continue
                if config['type'] == 'episodes' and 'episodes' not in show:
                    log.debug('Not submitting `%s`, no episode number found.' % entry['title'])
                    continue
                found.setdefault('shows', []).append(show)
            elif config['type'] in ['auto', 'movies']:
                movie = {'ids': get_entry_ids(entry)}
                if not movie['ids']:
                    if entry.get('movie_name') is not None:
                        movie['title'] = entry.get('movie_name') or entry.get('imdb_name')
                        movie['year'] = entry.get('movie_year') or entry.get('imdb_year')
                    else:
                        log.debug('Not submitting `%s`, no movie name or id found.' % entry['title'])
                        continue
                found.setdefault('movies', []).append(movie)

        if not (found['shows'] or found['movies']):
            log.debug('Nothing to submit to trakt.')
            return

        if config['list'] in ['collection', 'watchlist', 'watched']:
            args = ('sync', 'history' if config['list'] == 'watched' else config['list'])
        else:
            args = ('users', config['username'], 'lists', make_list_slug(config['list']), 'items')
        if remove:
            args += ('remove', )
        url = get_api_url(args)

        session = get_session(account=config.get('account'))
        log.debug('Submitting data to trakt.tv (%s): %s' % (url, found))
        try:
            result = session.post(url, data=json.dumps(found), raise_status=False)
        except RequestException as e:
            log.error('Error submitting data to trakt.tv: %s' % e)
            return
        if 200 <= result.status_code < 300:
            action = 'deleted' if remove else 'added'
            res = result.json()
            movies = res[action].get('movies', 0)
            shows = res[action].get('shows', 0)
            eps = res[action].get('episodes', 0)
            log.info('Successfully %s to/from list %s: %s movie(s), %s show(s), %s episode(s).',
                          action, config['list'], movies, shows, eps)
            for k, r in res['not_found'].iteritems():
                if r:
                    log.debug('not found %s: %s' % (k, r))
            # TODO: Improve messages about existing and unknown results
        elif result.status_code == 404:
            log.error('List does not appear to exist on trakt: %s' % config['list'])
        elif result.status_code == 401:
            log.error('Authentication error: have you authorized Flexget on Trakt.tv?')
            log.debug('trakt response: ' + result.text)
        else:
            log.error('Unknown error submitting data to trakt.tv: %s' % result.text)

    @staticmethod
    def add_entries(config, entries):
        TraktList.submit(config, entries, remove=False)

    @staticmethod
    def remove_entries(config, entries):
        TraktList.submit(config, entries, remove=False)

    @staticmethod
    def list_entries(config):
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

    def on_task_input(self, task, config):
        return self.list_entries(config)


class TraktAdd(object):
    """Add all accepted elements in your trakt.tv watchlist/library/seen or custom list."""
    schema = TraktList.schema

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        if task.manager.options.test:
            log.info('Not submitting to trakt.tv because of test mode.')
            return
        TraktList.add_entries(config, task.accepted)


class TraktRemove(object):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    schema = TraktList.schema

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        if task.manager.options.test:
            log.info('Not submitting to trakt.tv because of test mode.')
            return
        TraktList.remove_entries(config, task.accepted)


@event('plugin.register')
def register_plugin():
    plugin.register(TraktList, 'trakt_list', api_ver=2, groups=['list'])
    plugin.register(TraktAdd, 'trakt_add', api_ver=2)
    plugin.register(TraktRemove, 'trakt_remove', api_ver=2)
