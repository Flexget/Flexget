from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
import re

from path import Path

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.tools import TimedDict

log = logging.getLogger('exists_movie')


class FilterExistsMovie(object):
    """
    Reject existing movies.

    Syntax:

      exists_movie:
        path: /path/to/movies
        [type: {dirs|files}]
        [allow_different_qualities: {better|yes|no}]
        [lookup: {imdb|no}]
    """

    schema = {
        'anyOf': [
            one_or_more({'type': 'string', 'format': 'path'}),
            {
                'type': 'object',
                'properties': {
                    'path': one_or_more({'type': 'string', 'format': 'path'}),
                    'allow_different_qualities': {
                        'enum': ['better', True, False],
                        'default': False,
                    },
                    'type': {'enum': ['files', 'dirs'], 'default': 'dirs'},
                    'lookup': {'enum': ['imdb', False], 'default': False},
                },
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    dir_pattern = re.compile('\b(cd.\d|subs?|samples?)\b', re.IGNORECASE)
    file_pattern = re.compile('\.(avi|mkv|mp4|mpg|webm)$', re.IGNORECASE)

    def __init__(self):
        self.cache = TimedDict(cache_time='1 hour')

    def prepare_config(self, config):
        # if config is not a dict, assign value to 'path' key
        if not isinstance(config, dict):
            config = {'path': config}

        if not config.get('type'):
            config['type'] = 'dirs'

        # if only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], basestring):
            config['path'] = [config['path']]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return

        config = self.prepare_config(config)
        imdb_lookup = plugin.get('imdb_lookup', self)

        incompatible_files = 0
        incompatible_entries = 0
        count_entries = 0
        count_files = 0

        # list of imdb ids gathered from paths / cache
        qualities = {}

        for folder in config['path']:
            folder = Path(folder).expanduser()
            # see if this path has already been scanned
            cached_qualities = self.cache.get(folder, None)
            if cached_qualities:
                log.verbose('Using cached scan for %s ...' % folder)
                qualities.update(cached_qualities)
                continue

            path_ids = {}

            if not folder.isdir():
                log.critical('Path %s does not exist' % folder)
                continue

            log.verbose('Scanning path %s ...' % folder)

            # Help debugging by removing a lot of noise
            # logging.getLogger('movieparser').setLevel(logging.WARNING)
            # logging.getLogger('imdb_lookup').setLevel(logging.WARNING)

            # scan through
            items = []
            if config.get('type') == 'dirs':
                for d in folder.walkdirs(errors='ignore'):
                    if self.dir_pattern.search(d.name):
                        continue
                    log.debug('detected dir with name %s, adding to check list' % d.name)
                    items.append(d.name)
            elif config.get('type') == 'files':
                for f in folder.walkfiles(errors='ignore'):
                    if not self.file_pattern.search(f.name):
                        continue
                    log.debug('detected file with name %s, adding to check list' % f.name)
                    items.append(f.name)

            if not items:
                log.verbose(
                    'No items with type %s were found in %s' % (config.get('type'), folder)
                )
                continue

            for item in items:
                count_files += 1

                movie = plugin.get('parsing', self).parse_movie(item)

                if config.get('lookup') == 'imdb':
                    try:
                        imdb_id = imdb_lookup.imdb_id_lookup(
                            movie_title=movie.name,
                            movie_year=movie.year,
                            raw_title=item,
                            session=task.session,
                        )
                        if imdb_id in path_ids:
                            log.trace('duplicate %s' % item)
                            continue
                        if imdb_id is not None:
                            log.trace('adding: %s' % imdb_id)
                            path_ids[imdb_id] = movie.quality
                    except plugin.PluginError as e:
                        log.trace('%s lookup failed (%s)' % (item, e.value))
                        incompatible_files += 1
                else:
                    path_ids[movie.name] = movie.quality
                    log.trace('adding: %s' % movie.name)

            # store to cache and extend to found list
            self.cache[folder] = path_ids
            qualities.update(path_ids)

        log.debug('-- Start filtering entries ----------------------------------')

        # do actual filtering
        for entry in task.accepted:
            count_entries += 1
            log.debug('trying to parse entry %s' % entry['title'])
            if config.get('lookup') == 'imdb':
                key = 'imdb_id'
                if not entry.get('imdb_id', eval_lazy=False):
                    try:
                        imdb_lookup.lookup(entry)
                    except plugin.PluginError as e:
                        log.trace('entry %s imdb failed (%s)' % (entry['title'], e.value))
                        incompatible_entries += 1
                        continue
            else:
                key = 'movie_name'
                if not entry.get('movie_name', eval_lazy=False):
                    movie = plugin.get('parsing', self).parse_movie(entry['title'])
                    entry['movie_name'] = movie.name

            # actual filtering
            if entry[key] in qualities:
                if config.get('allow_different_qualities') == 'better':
                    if entry['quality'] > qualities[entry[key]]:
                        log.trace('better quality')
                        continue
                elif config.get('allow_different_qualities'):
                    if entry['quality'] != qualities[entry[key]]:
                        log.trace('wrong quality')
                        continue

                entry.reject('movie exists')

        if incompatible_files or incompatible_entries:
            log.verbose(
                'There were some incompatible items. %s of %s entries '
                'and %s of %s directories could not be verified.'
                % (incompatible_entries, count_entries, incompatible_files, count_files)
            )

        log.debug('-- Finished filtering entries -------------------------------')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterExistsMovie, 'exists_movie', interfaces=['task'], api_ver=2)
