from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.api_trakt import get_session, make_list_slug, get_api_url

log = logging.getLogger('trakt_emit')


class TraktEmit(object):
    """
    Creates an entry for the latest or the next item in your watched or collected
    episodes in your trakt account.

    Syntax:

    trakt_emit:
      account: <value>
      username: <value>
      position: <last|next>
      context: <collect|collected|watch|watched>
      list: <value>

    `account` option is required if the profile is private. `username` will default to account owner if `account` is
    specified.

    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'account': {'type': 'string'},
            'position': {'type': 'string', 'enum': ['last', 'next'], 'default': 'next'},
            'context': {'type': 'string', 'enum': ['watched', 'collected'], 'default': 'watched'},
            'list': {'type': 'string'},
            'strip_dates': {'type': 'boolean', 'default': False}
        },
        'anyOf': [{'required': ['username']}, {'required': ['account']}],
        'error_anyOf': 'At least one of `username` or `account` options are needed.',
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        if config.get('account') and not config.get('username'):
            config['username'] = 'me'
        session = get_session(account=config.get('account'))
        listed_series = {}
        if config.get('list'):
            args = ('users', config['username'])
            if config['list'] in ['collection', 'watchlist', 'watched']:
                args += (config['list'], 'shows')
            else:
                args += ('lists', make_list_slug(config['list']), 'items')
            try:
                data = session.get(get_api_url(args)).json()
            except RequestException as e:
                raise plugin.PluginError('Unable to get trakt list `%s`: %s' % (config['list'], e))
            if not data:
                log.warning('The list "%s" is empty.' % config['list'])
                return
            for item in data:
                if item.get('show'):
                    if not item['show']['title']:
                        # Seems we can get entries with a blank show title sometimes
                        log.warning('Found trakt list show with no series name.')
                        continue
                    trakt_id = item['show']['ids']['trakt']
                    listed_series[trakt_id] = {
                        'series_name': '%s (%s)' % (item['show']['title'], item['show']['year']),
                        'trakt_id': trakt_id,
                        'tvdb_id': item['show']['ids']['tvdb'],
                        'trakt_list': config.get('list')}
        context = config['context']
        if context == 'collected':
            context = 'collection'
        entries = []
        for trakt_id, fields in listed_series.items():
            url = get_api_url('shows', trakt_id, 'progress', context)
            try:
                data = session.get(url).json()
            except RequestException as e:
                raise plugin.PluginError('TODO: error message')
            if config['position'] == 'next' and data.get('next_episode'):
                # If the next episode is already in the trakt database, we'll get it here
                eps = data['next_episode']['season']
                epn = data['next_episode']['number']
            else:
                # If we need last ep, or next_episode was not provided, search for last ep
                for seas in reversed(data['seasons']):
                    # Find the first season with collected/watched episodes
                    if seas['completed'] > 0:
                        eps = seas['number']
                        # Pick the highest collected/watched episode
                        epn = max(item['number'] for item in seas['episodes'] if item['completed'])
                        # If we are in next episode mode, we have to increment this number
                        if config['position'] == 'next':
                            if seas['completed'] >= seas['aired']:
                                # TODO: next_episode doesn't count unaired episodes right now, this will skip to next
                                # season too early when there are episodes left to air this season.
                                eps += 1
                                epn = 1
                            else:
                                epn += 1
                        break
                else:
                    if config['position'] == 'next':
                        eps = epn = 1
                    else:
                        # There were no watched/collected episodes, nothing to emit in 'last' mode
                        continue
            if eps and epn:
                if config.get('strip_dates'):
                    # remove year from end of series_name if present
                    fields['series_name'] = re.sub(r'\s+\(\d{4}\)$', '', fields['series_name'])
                entry = self.make_entry(fields, eps, epn)
                entries.append(entry)
        return entries

    def make_entry(self, fields, season, episode):
        entry = Entry()
        entry.update(fields)
        entry['series_season'] = season
        entry['series_episode'] = episode
        entry['series_id_type'] = 'ep'
        entry['series_id'] = 'S%02dE%02d' % (season, episode)
        entry['title'] = entry['series_name'] + ' ' + entry['series_id']
        entry['url'] = 'http://trakt.tv/shows/%s/seasons/%s/episodes/%s' % (fields['trakt_id'], season, episode)
        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(TraktEmit, 'trakt_emit', api_ver=2)
