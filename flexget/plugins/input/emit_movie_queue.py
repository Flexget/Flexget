from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.imdb import make_url as make_imdb_url

try:
    from flexget.plugins.filter.movie_queue import queue_get
except ImportError:
    raise plugin.DependencyError(issued_by='emit_movie_queue', missing='movie_queue')

log = logging.getLogger('emit_movie_queue')


class EmitMovieQueue(object):
    """Use your movie queue as an input by emitting the content of it"""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'year': {'type': 'boolean'},
                    'quality': {'type': 'boolean'},
                    'queue_name': {'type': 'string'}
                },
                'additionalProperties': False,
                'deprecated': 'movie_queue plugin is deprecated. Please switch to using movie_list'
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        config.setdefault('year', True)
        config.setdefault('quality', False)
        config.setdefault('queue_name', 'default')
        return config

    def on_task_input(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)
        entries = []
        queue_name = config.get('queue_name')

        with Session() as session:
            for queue_item in queue_get(session=session, downloaded=False, queue_name=queue_name):
                entry = Entry()
                # make sure the entry has IMDB fields filled
                entry['url'] = ''
                if queue_item.imdb_id:
                    entry['imdb_id'] = queue_item.imdb_id
                    entry['imdb_url'] = make_imdb_url(queue_item.imdb_id)
                if queue_item.tmdb_id:
                    entry['tmdb_id'] = queue_item.tmdb_id

                # check if title is a imdb url (leftovers from old database?)
                # TODO: maybe this should be fixed at the queue_get ...
                if 'http://' in queue_item.title:
                    plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
                    log.debug('queue contains url instead of title')
                    if entry.get('movie_name'):
                        entry['title'] = entry['movie_name']
                    else:
                        log.error('Found imdb url in imdb queue, but lookup failed: %s' % entry['title'])
                        continue
                else:
                    # normal title
                    entry['title'] = queue_item.title

                # Add the year and quality if configured to (make sure not to double it up)
                if config.get('year') and entry.get('movie_year') \
                        and str(entry['movie_year']) not in entry['title']:
                    plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
                    entry['title'] += ' %s' % entry['movie_year']
                # TODO: qualities can now be ranges.. how should we handle this?
                if config.get('quality') and queue_item.quality != 'ANY':
                    log.info('quality option of emit_movie_queue is disabled while we figure out how to handle ranges')
                    # entry['title'] += ' %s' % queue_item.quality
                entries.append(entry)
                if entry.get('imdb_id'):
                    log.debug('Added title and IMDB id to new entry: %s - %s',
                              entry['title'], entry['imdb_id'])
                elif entry.get('tmdb_id'):
                    log.debug('Added title and TMDB id to new entry: %s - %s',
                              entry['title'], entry['tmdb_id'])
                else:
                    # should this ever happen though?
                    log.debug('Added title to new entry: %s', entry['title'])

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(EmitMovieQueue, 'emit_movie_queue', api_ver=2)
