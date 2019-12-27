import re
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.tools import TimedDict

logger = logger.bind(name='exists_movie')


class FilterExistsMovie:
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

    dir_pattern = re.compile(r'\b(cd.\d|subs?|samples?)\b', re.IGNORECASE)
    file_pattern = re.compile(r'\.(avi|mkv|mp4|mpg|webm)$', re.IGNORECASE)

    def __init__(self):
        self.cache = TimedDict(cache_time='1 hour')

    def prepare_config(self, config):
        # if config is not a dict, assign value to 'path' key
        if not isinstance(config, dict):
            config = {'path': config}

        if not config.get('type'):
            config['type'] = 'dirs'

        # if only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], str):
            config['path'] = [config['path']]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            logger.debug('nothing accepted, aborting')
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
                logger.verbose('Using cached scan for {} ...', folder)
                qualities.update(cached_qualities)
                continue

            path_ids = {}

            if not folder.is_dir():
                logger.critical('Path {} does not exist', folder)
                continue

            logger.verbose('Scanning path {} ...', folder)

            # Help debugging by removing a lot of noise
            # logging.getLogger('movieparser').setLevel(logging.WARNING)
            # logging.getLogger('imdb_lookup').setLevel(logging.WARNING)

            # scan through
            items = []
            for p in folder.iterdir():
                if config.get('type') == 'dirs' and p.is_dir():
                    if self.dir_pattern.search(p.name):
                        continue
                    logger.debug('detected dir with name {}, adding to check list', p.name)
                    items.append(p.name)
                elif config.get('type') == 'files' and p.is_file():
                    if not self.file_pattern.search(p.name):
                        continue
                    logger.debug('detected file with name {}, adding to check list', p.name)
                    items.append(p.name)

            if not items:
                logger.verbose(
                    'No items with type {} were found in {}', config.get('type'), folder
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
                            logger.trace('duplicate {}', item)
                            continue
                        if imdb_id is not None:
                            logger.trace('adding: {}', imdb_id)
                            path_ids[imdb_id] = movie.quality
                    except plugin.PluginError as e:
                        logger.trace('{} lookup failed ({})', item, e.value)
                        incompatible_files += 1
                else:
                    movie_id = movie.name
                    if movie.name is not None and movie.year is not None:
                        movie_id = "%s %s" % (movie.name, movie.year)
                    path_ids[movie_id] = movie.quality
                    logger.trace('adding: {}', movie_id)

            # store to cache and extend to found list
            self.cache[folder] = path_ids
            qualities.update(path_ids)

        logger.debug('-- Start filtering entries ----------------------------------')

        # do actual filtering
        for entry in task.accepted:
            count_entries += 1
            logger.debug('trying to parse entry {}', entry['title'])
            if config.get('lookup') == 'imdb':
                key_imdb = 'imdb_id'
                if not entry.get(key_imdb, eval_lazy=False):
                    try:
                        imdb_lookup.lookup(entry)
                    except plugin.PluginError as e:
                        logger.trace('entry {} imdb failed ({})', entry['title'], e.value)
                        incompatible_entries += 1
                        continue
                key = entry[key_imdb]
            else:
                key_name = 'movie_name'
                key_year = 'movie_year'
                if not entry.get(key_name, eval_lazy=False):
                    movie = plugin.get('parsing', self).parse_movie(entry['title'])
                    entry[key_name] = movie.name
                    entry[key_year] = movie.year

                if entry.get(key_year, eval_lazy=False):
                    key = "%s %s" % (entry[key_name], entry[key_year])
                else:
                    key = entry[key_name]

            # actual filtering
            if key in qualities:
                if config.get('allow_different_qualities') == 'better':
                    if entry['quality'] > qualities[key]:
                        logger.trace('better quality')
                        continue
                elif config.get('allow_different_qualities'):
                    if entry['quality'] != qualities[key]:
                        logger.trace('wrong quality')
                        continue

                entry.reject('movie exists')

        if incompatible_files or incompatible_entries:
            logger.verbose(
                'There were some incompatible items. {} of {} entries and {} of {} directories could not be verified.',
                incompatible_entries,
                count_entries,
                incompatible_files,
                count_files,
            )

        logger.debug('-- Finished filtering entries -------------------------------')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterExistsMovie, 'exists_movie', interfaces=['task'], api_ver=2)
