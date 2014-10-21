from __future__ import unicode_literals, division, absolute_import
import os
import logging

from path import path

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.plugin import get_plugin_by_name
from flexget.utils.tools import TimedDict

log = logging.getLogger('exists_movie')


class FilterExistsMovie(object):

    """
    Reject existing movies.

    Example::

      exists_movie: /storage/movies/
    """

    schema = one_or_more({'type': 'string', 'format': 'path'})

    skip = ['cd1', 'cd2', 'subs', 'sample']

    def __init__(self):
        self.cache = TimedDict(cache_time='1 hour')

    def build_config(self, config):
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return

        config = self.build_config(config)
        imdb_lookup = plugin.get_plugin_by_name('imdb_lookup').instance

        incompatible_dirs = 0
        incompatible_entries = 0
        count_entries = 0
        count_dirs = 0

        # list of imdb ids gathered from paths / cache
        imdb_ids = []

        for folder in config:
            folder = path(folder).expanduser()
            # see if this path has already been scanned
            if folder in self.cache:
                log.verbose('Using cached scan for %s ...' % folder)
                imdb_ids.extend(self.cache[folder])
                continue

            path_ids = []

            if not folder.isdir():
                log.critical('Path %s does not exist' % folder)
                continue

            log.verbose('Scanning path %s ...' % folder)

            # Help debugging by removing a lot of noise
            #logging.getLogger('movieparser').setLevel(logging.WARNING)
            #logging.getLogger('imdb_lookup').setLevel(logging.WARNING)

            # scan through

            # TODO: add also video files?
            for item in folder.walkdirs(errors='ignore'):
                if item.name.lower() in self.skip:
                    continue
                count_dirs += 1

                movie = get_plugin_by_name('parsing').instance.parse_movie(item)

                try:
                    imdb_id = imdb_lookup.imdb_id_lookup(movie_title=movie.name,
                                                         raw_title=item.name,
                                                         session=task.session)
                    if imdb_id in path_ids:
                        log.trace('duplicate %s' % item)
                        continue
                    if imdb_id is not None:
                        log.trace('adding: %s' % imdb_id)
                        path_ids.append(imdb_id)
                except plugin.PluginError as e:
                    log.trace('%s lookup failed (%s)' % (item, e.value))
                    incompatible_dirs += 1

            # store to cache and extend to found list
            self.cache[folder] = path_ids
            imdb_ids.extend(path_ids)

        log.debug('-- Start filtering entries ----------------------------------')

        # do actual filtering
        for entry in task.accepted:
            count_entries += 1
            if not entry.get('imdb_id', eval_lazy=False):
                try:
                    imdb_lookup.lookup(entry)
                except plugin.PluginError as e:
                    log.trace('entry %s imdb failed (%s)' % (entry['title'], e.value))
                    incompatible_entries += 1
                    continue

            # actual filtering
            if entry['imdb_id'] in imdb_ids:
                entry.reject('movie exists')

        if incompatible_dirs or incompatible_entries:
            log.verbose('There were some incompatible items. %s of %s entries '
                        'and %s of %s directories could not be verified.' %
                (incompatible_entries, count_entries, incompatible_dirs, count_dirs))

        log.debug('-- Finished filtering entries -------------------------------')

@event('plugin.register')
def register_plugin():
    plugin.register(FilterExistsMovie, 'exists_movie', groups=['exists'], api_ver=2)
