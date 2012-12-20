from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.entry import Entry
from flexget.plugin import register_plugin, get_plugin_by_name, DependencyError

try:
    from flexget.plugins.filter.movie_queue import queue_get
except ImportError:
    raise DependencyError(issued_by='emit_movie_queue', missing='movie_queue')

log = logging.getLogger('emit_movie_queue')


class EmitIMDBQueue(object):
    """Use your imdb queue as an input by emitting the content of it"""

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        advanced = root.accept('dict')
        advanced.accept('boolean', key='year')
        advanced.accept('boolean', key='quality')
        return root

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'year': True, 'quality': True}
        return config

    def on_task_input(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)

        entries = []
        imdb_entries = queue_get()

        for imdb_entry in imdb_entries:
            entry = Entry()
            # make sure the entry has IMDB fields filled
            entry['url'] = ''
            entry['imdb_url'] = 'http://www.imdb.com/title/' + imdb_entry.imdb_id
            entry['imdb_id'] = imdb_entry.imdb_id

            get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
            # check if title is a imdb url (leftovers from old database?)
            # TODO: maybe this should be fixed at the queue_get ...
            if 'http://' in imdb_entry.title:
                log.debug('queue contains url instead of title')
                if entry.get('movie_name'):
                    entry['title'] = entry['movie_name']
                else:
                    log.error('Found imdb url in imdb queue, but lookup failed: %s' % entry['title'])
                    continue
            else:
                # normal title
                entry['title'] = imdb_entry.title

            # Add the year and quality if configured to
            if config.get('year') and entry.get('movie_year'):
                entry['title'] += ' %s' % entry['movie_year']
            # TODO: qualities can now be ranges.. how should we handle this?
            #if config.get('quality') and imdb_entry.quality != 'ANY':
            #    entry['title'] += ' %s' % imdb_entry.quality
            entries.append(entry)
            log.debug('Added title and IMDB id to new entry: %s - %s' %
                     (entry['title'], entry['imdb_id']))

        return entries

register_plugin(EmitIMDBQueue, 'emit_movie_queue', api_ver=2)
