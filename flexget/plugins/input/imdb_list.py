from __future__ import unicode_literals, division, absolute_import
import logging
import re

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
        if rss.get('status') == 404:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        # Create an Entry for each movie in the list
        entries = []
        title_re = re.compile(r'(.*) \((\d{4})?.*?\)$')
        for entry in rss.entries:
            try:
                # IMDb puts some extra stuff in the titles, e.g. "Battlestar Galactica (2004 TV Series)"
                # Strip out everything but the date
                match = title_re.match(entry.title)
                title = match.group(1)
                if match.group(2):
                    title += ' (%s)' % match.group(2)
                entries.append(
                    Entry(title=title, url=entry.link, imdb_id=extract_id(entry.link), imdb_name=match.group(1)))
            except IndexError:
                log.critical('IndexError! Unable to handle RSS entry: %s' % entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2)
