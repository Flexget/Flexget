from __future__ import unicode_literals, division, absolute_import
import logging

import feedparser

from flexget import plugin
from flexget.event import event
from flexget.utils.imdb import extract_id
from flexget.utils.cached_input import cached
from flexget.entry import Entry

log = logging.getLogger('imdb_list')

USER_ID_RE = r'^ur\d{7,8}$'


class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'string',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form urXXXXXXX'
            },
            'list': {'type': 'string'}
        },
        'required': ['list', 'user_id'],
        'additionalProperties': False
    }

    @cached('imdb_list', persist='2 hours')
    def on_task_input(self, task, config):
        log.verbose('Retrieving list %s ...' % config['list'])

        # Get the imdb list in RSS format
        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://rss.imdb.com/user/%s/%s' % (config['user_id'], config['list'])
        else:
            url = 'http://rss.imdb.com/list/%s' % config['list']
        log.debug('Requesting %s' % url)
        try:
            rss = feedparser.parse(url)
        except LookupError as e:
            raise plugin.PluginError('Failed to parse RSS feed for list `%s` correctly: %s' % (config['list'], e))
        if rss.status == 404:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        # Create an Entry for each movie in the list
        entries = []
        for entry in rss.entries:
            try:
                entries.append(Entry(title=entry.title, url=entry.link, imdb_id=extract_id(entry.link), imdb_name=entry.title))
            except IndexError:
                log.critical('IndexError! Unable to handle RSS entry: %s' % entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2)
