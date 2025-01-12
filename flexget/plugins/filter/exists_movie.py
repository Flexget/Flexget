import re
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.tools import TimedDict

logger = logger.bind(name='exists_movie')


def merge_found_qualities(existing_qualities: dict[str, set], new_qualities: dict[str, set]):
    """Merge the qualities from new_qualities dict into existing_qualities dict."""
    for movie_id, quals in new_qualities.items():
        existing_qualities.setdefault(movie_id, set()).update(quals)


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
        self.cache: dict[Path, dict[str, set]] = TimedDict(cache_time='1 hour')

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

        # Maps movie identifier: set of found qualitites
        existing_qualities: dict[str, set] = {}

        for folder in config['path']:
            folder = Path(folder).expanduser()
            # see if this path has already been scanned
            cached_qualities = self.cache.get(folder, None)
            if cached_qualities:
                logger.verbose('Using cached scan for {} ...', folder)
                merge_found_qualities(existing_qualities, cached_qualities)
                continue

            path_qualities: dict[str, set] = {}

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
                        movie_id = imdb_lookup.imdb_id_lookup(
                            movie_title=movie.name,
                            movie_year=movie.year,
                            raw_title=item,
                            session=task.session,
                        )
                    except plugin.PluginError as e:
                        logger.trace('{} lookup failed ({})', item, e.value)
                        incompatible_files += 1
                        continue
                else:
                    movie_id = movie.name
                    if movie.name is not None and movie.year is not None:
                        movie_id = f"{movie.name} {movie.year}"
                if movie_id is not None:
                    path_qualities.setdefault(movie_id, set()).add(movie.quality)
                    logger.trace('adding: {}', movie_id)

            # store to cache and extend to found list
            self.cache[folder] = path_qualities
            merge_found_qualities(existing_qualities, path_qualities)

        logger.debug('-- Start filtering entries ----------------------------------')

        # do actual filtering
        for entry in task.accepted:
            count_entries += 1
            logger.debug('trying to parse entry {}', entry['title'])
            if config.get('lookup') == 'imdb':
                if not entry.get('imdb_id', eval_lazy=False):
                    try:
                        imdb_lookup.lookup(entry)
                    except plugin.PluginError as e:
                        logger.trace('entry {} imdb failed ({})', entry['title'], e.value)
                        incompatible_entries += 1
                        continue
                movie_id = entry['imdb_id']
            else:
                if not entry.get('movie_name', eval_lazy=False):
                    movie = plugin.get('parsing', self).parse_movie(entry['title'])
                    entry['movie_name'] = movie.name
                    entry['movie_year'] = movie.year

                if entry.get('movie_year', eval_lazy=False):
                    movie_id = f"{entry['movie_name']} {entry['movie_year']}"
                else:
                    movie_id = entry['movie_name']

            # actual filtering
            if movie_id in existing_qualities:
                if config.get('allow_different_qualities') == 'better':
                    if all(entry['quality'] > qual for qual in existing_qualities[movie_id]):
                        logger.trace('better quality')
                        continue
                elif (
                    config.get('allow_different_qualities')
                    and entry['quality'] not in existing_qualities[movie_id]
                ):
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
