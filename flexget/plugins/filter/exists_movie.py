import os
import logging
from flexget.plugin import register_plugin, priority, PluginError, get_plugin_by_name
from flexget.utils.imdb import extract_id
from flexget.utils.titles.movie import MovieParser

log = logging.getLogger('exists_movie')


class FilterExistsMovie(object):

    """
        Reject existing movies.

        Example:

        exists_movie: /storage/movies/
    """

    skip = ['cd1', 'cd2', 'subs', 'sample']

    def __init__(self):
        self.cache = {}

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('path')
        bundle = root.accept('list')
        bundle.accept('path')
        return root

    def build_config(self, config):
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    def on_process_start(self, feed, config):
        self.cache = {}

    @priority(-1)
    def on_feed_filter(self, feed, config):
        if not feed.accepted:
            log.debug('nothing accepted, aborting')
            return

        config = self.build_config(config)
        imdb_lookup = get_plugin_by_name('imdb_lookup').instance

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

            # scan through
            for root, dirs, files in os.walk(path):
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
                                                             session=feed.session)
                        if imdb_id in path_ids:
                            log.trace('duplicate %s' % item)
                            continue
                        if imdb_ids is not None:
                            path_ids.append(imdb_id)
                    except PluginError, e:
                        log.trace('%s lookup failed (%s)' % (item, e.value))
                        incompatible_dirs += 1

            # store to cache
            self.cache[path] = path_ids

        log.debug('-- Start filtering entries ----------------------------------')

        # do actual filtering
        for entry in feed.accepted:
            count_entries += 1
            if not entry.get('imdb_id', lazy=False):
                try:
                    imdb_lookup.lookup(entry)
                except PluginError, e:
                    log.trace('entry %s imdb failed (%s)' % (entry['title'], e.value))
                    incompatible_entries += 1
                    continue

            # actual filtering
            if entry['imdb_id'] in imdb_ids:
                feed.reject(entry, 'movie exists')

        if incompatible_dirs or incompatible_entries:
            log.verbose('There were some incompatible items. %s of %s entries and %s of %s directories could not be verified.' %
                (incompatible_entries, count_entries, incompatible_dirs, count_dirs))

register_plugin(FilterExistsMovie, 'exists_movie', groups=['exists'], api_ver=2)
