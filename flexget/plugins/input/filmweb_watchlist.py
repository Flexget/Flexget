from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.entry import Entry


try:
    from filmweb.filmweb import Filmweb as FilmwebAPI
    from filmweb.items import LoggedUser
    from filmweb.exceptions import RequestFailed
except ImportError:
    # Errors are handled later
    pass


log = logging.getLogger('filmweb_watchlist')


def translate_type(type):
    return {'shows': 'serial', 'movies': 'film'}[type]


class FilmwebWatchlist(object):
    """"Creates an entry for each movie in your Filmweb list."""

    schema = {
        'type': 'object',
        'properties': {
            'login': {'type': 'string', 'description': 'Can be username or email address'},
            'password': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['shows', 'movies'], 'default': 'movies'},
            'min_star': {
                'type': 'integer',
                'default': 0,
                'description': 'Items will be processed with at least this level of "How much I want to see"'
            }
        },
        'additionalProperties': False,
        'required': ['login', 'password'],
    }

    def on_task_start(self, task, config):
        """Raise a DependencyError if our dependencies aren't available"""
        try:
            from filmweb.filmweb import Filmweb as FilmwebAPI # noqa
        except ImportError as e:
            log.debug('Error importing pyfilmweb: %s' % e)
            raise plugin.DependencyError('filmweb_watchlist', 'pyfilmweb',
                                         'pyfilmweb==0.1.1.1 module required. ImportError: %s' % e,
                                         log)

    @cached('filmweb_watchlist', persist='2 hours')
    def on_task_input(self, task, config):
        type = translate_type(config['type'])

        log.verbose('Retrieving filmweb watch list for user: %s', config['login'])

        fw = FilmwebAPI()
        log.verbose('Logging as %s', config['login'])

        try:
            fw.login(str(config['login']), str(config['password']))
        except RequestFailed as error:
            raise plugin.PluginError('Authentication request failed, reason %s' % str(error))

        user = LoggedUser(fw)

        try:
            watch_list = user.get_want_to_see()
        except RequestFailed as error:
            raise plugin.PluginError('Fetching watch list failed, reason %s' % str(error))

        log.verbose('Filmweb list contains %s items', len(watch_list))

        entries = []
        for item in watch_list:
            if item['level'] < config['min_star']:
                continue

            if item['film'].type != type:
                continue

            item_info = item['film'].get_info()

            entry = Entry()
            entry['title'] = item_info['name_org'] or item_info['name']
            entry['title'] += ' (%s)' % item_info['year']
            entry['year'] = item_info['year']
            entry['url'] = item['film'].url
            entry['filmweb_type'] = item_info['type']
            entry['filmweb_id'] = item['film'].uid

            log.debug('Created entry %s', entry)

            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(FilmwebWatchlist, 'filmweb_watchlist', api_ver=2)
