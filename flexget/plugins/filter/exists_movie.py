from __future__ import unicode_literals, division, absolute_import
import os
import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.titles.movie import MovieParser
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

        for path in config:
            # see if this path has already been scanned
            if path in self.cache:
                log.verbose('Using cached scan for %s ...' % path)
                imdb_ids.extend(self.cache[path])
                continue

            path_ids = []

            # with unicode it crashes on some paths ..
            path = str(os.path.expanduser(path))
            if not os.path.exists(path):
                log.critical('Path %s does not exist' % path)
                continue

            log.verbose('Scanning path %s ...' % path)

            # Help debugging by removing a lot of noise
            #logging.getLogger('movieparser').setLevel(logging.WARNING)
            #logging.getLogger('imdb_lookup').setLevel(logging.WARNING)

            # scan through
            for root, dirs, files in os.walk(path, followlinks=True):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                # files = [x.decode('utf-8', 'ignore') for x in files]

                # TODO: add also video files?
                for item in dirs:
                    if item.lower() in self.skip:
                        continue
                    count_dirs += 1

                    movie = MovieParser()
                    movie.parse(item)

                    try:
                        imdb_id = imdb_lookup.imdb_id_lookup(movie_title=movie.name,
                                                             raw_title=item,
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
            self.cache[path] = path_ids
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
