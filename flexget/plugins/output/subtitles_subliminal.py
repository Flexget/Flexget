import collections
import logging
import os
import sys
import tempfile

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='subtitles')

try:
    from subliminal.extensions import provider_manager

    PROVIDERS = provider_manager.names()
except ImportError:
    PROVIDERS = [
        'argenteam',
        'legendastv',
        'opensubtitles',
        'opensubtitlesvip',
        'podnapisi',
        'shooter',
        'thesubdb',
        'tvsubtitles',
    ]

AUTHENTICATION_SCHEMA = dict((provider, {'type': 'object'}) for provider in PROVIDERS)


class PluginSubliminal:
    r"""
    Search and download subtitles using Subliminal by Antoine Bertin
    (https://pypi.python.org/pypi/subliminal).

    Example (complete task)::

      subs:
        find:
          path:
            - d:\media\incoming
          regexp: '.*\.(avi|mkv|mp4)$'
          recursive: yes
        accept_all: yes
        subliminal:
          languages:
            - ita
          alternatives:
            - eng
          exact_match: no
          providers: legendastv, opensubtitles
          single: no
          directory: /disk/subtitles
          hearing_impaired: yes
          authentication:
            legendastv:
              username: myuser
              passsword: mypassword
    """

    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
            'exact_match': {'type': 'boolean', 'default': True},
            'providers': {'type': 'array', 'items': {'type': 'string', 'enum': PROVIDERS}},
            'single': {'type': 'boolean', 'default': True},
            'directory': {'type:': 'string'},
            'hearing_impaired': {'type': 'boolean', 'default': False},
            'authentication': {'type': 'object', 'properties': AUTHENTICATION_SCHEMA},
        },
        'required': ['languages'],
        'additionalProperties': False,
    }

    def on_task_start(self, task, config):
        if list(sys.version_info) < [2, 7]:
            raise plugin.DependencyError(
                'subliminal', 'Python 2.7', 'Subliminal plugin requires python 2.7.'
            )
        try:
            import babelfish  # noqa
        except ImportError as e:
            logger.debug('Error importing Babelfish: {}', e)
            raise plugin.DependencyError(
                'subliminal', 'babelfish', 'Babelfish module required. ImportError: %s' % e
            )
        try:
            import subliminal  # noqa
        except ImportError as e:
            logger.debug('Error importing Subliminal: {}', e)
            raise plugin.DependencyError(
                'subliminal', 'subliminal', 'Subliminal module required. ImportError: %s' % e
            )

    def on_task_output(self, task, config):
        """
        Configuration::
            subliminal:
                languages: List of languages (as IETF codes) in order of preference. At least one is required.
                alternatives: List of second-choice languages; subs will be downloaded but entries rejected.
                exact_match: Use file hash only to search for subs, otherwise Subliminal will try to guess by filename.
                providers: List of providers from where to download subtitles.
                single: Download subtitles in single mode (no language code added to subtitle filename).
                directory: Path to directory where to save the subtitles, default is next to the video.
                hearing_impaired: Prefer subtitles for the hearing impaired when available
                authentication: >
                  Dictionary of configuration options for different providers.
                  Keys correspond to provider names, and values are dictionaries, usually specifying `username` and
                  `password`.
        """
        if not task.accepted:
            logger.debug('nothing accepted, aborting')
            return
        import subliminal
        from babelfish import Language
        from dogpile.cache.exception import RegionAlreadyConfigured
        from subliminal import save_subtitles, scan_video
        from subliminal.cli import MutexLock
        from subliminal.core import (
            ARCHIVE_EXTENSIONS,
            refine,
            scan_archive,
            search_external_subtitles,
        )
        from subliminal.score import episode_scores, movie_scores
        from subliminal.video import VIDEO_EXTENSIONS

        try:
            subliminal.region.configure(
                'dogpile.cache.dbm',
                arguments={
                    'filename': os.path.join(tempfile.gettempdir(), 'cachefile.dbm'),
                    'lock_factory': MutexLock,
                },
            )
        except RegionAlreadyConfigured:
            pass

        # Let subliminal be more verbose if our logger is set to DEBUG
        if logger.level(task.manager.options.loglevel).no <= logger.level('DEBUG').no:
            logging.getLogger("subliminal").setLevel(logging.INFO)
        else:
            logging.getLogger("subliminal").setLevel(logging.CRITICAL)

        logging.getLogger("dogpile").setLevel(logging.CRITICAL)
        logging.getLogger("enzyme").setLevel(logging.WARNING)
        try:
            languages = set([Language.fromietf(s) for s in config.get('languages', [])])
            alternative_languages = set(
                [Language.fromietf(s) for s in config.get('alternatives', [])]
            )
        except ValueError as e:
            raise plugin.PluginError(e)
        # keep all downloaded subtitles and save to disk when done (no need to write every time)
        downloaded_subtitles = collections.defaultdict(list)
        providers_list = config.get('providers', None)
        provider_configs = config.get('authentication', None)
        # test if only one language was provided, if so we will download in single mode
        # (aka no language code added to subtitle filename)
        # unless we are forced not to by configuration
        # if we pass 'yes' for single in configuration but choose more than one language
        # we ignore the configuration and add the language code to the
        # potentially downloaded files
        single_mode = config.get('single', '') and len(languages | alternative_languages) <= 1
        hearing_impaired = config.get('hearing_impaired', False)

        with subliminal.core.ProviderPool(
            providers=providers_list, provider_configs=provider_configs
        ) as provider_pool:
            for entry in task.accepted:
                if 'location' not in entry:
                    logger.warning('Cannot act on entries that do not represent a local file.')
                    continue
                if not os.path.exists(entry['location']):
                    entry.fail('file not found: %s' % entry['location'])
                    continue
                if '$RECYCLE.BIN' in entry['location']:  # ignore deleted files in Windows shares
                    continue

                try:
                    entry_languages = set(entry.get('subtitle_languages', [])) or languages

                    if entry['location'].endswith(VIDEO_EXTENSIONS):
                        video = scan_video(entry['location'])
                    elif entry['location'].endswith(ARCHIVE_EXTENSIONS):
                        video = scan_archive(entry['location'])
                    else:
                        entry.reject(
                            'File extension is not a supported video or archive extension'
                        )
                        continue
                    # use metadata refiner to get mkv metadata
                    refiner = ('metadata',)
                    refine(video, episode_refiners=refiner, movie_refiners=refiner)
                    existing_subtitles = set(search_external_subtitles(entry['location']).values())
                    video.subtitle_languages |= existing_subtitles
                    if isinstance(video, subliminal.Episode):
                        title = video.series
                        hash_scores = episode_scores['hash']
                    else:
                        title = video.title
                        hash_scores = movie_scores['hash']
                    logger.info('Name computed for {} was {}', entry['location'], title)
                    msc = hash_scores if config['exact_match'] else 0
                    if entry_languages.issubset(video.subtitle_languages):
                        logger.debug(
                            'All preferred languages already exist for "{}"', entry['title']
                        )
                        entry['subtitles_missing'] = set()
                        continue  # subs for preferred lang(s) already exists
                    else:
                        # Gather the subtitles for the alternative languages too, to avoid needing to search the sites
                        # again. They'll just be ignored if the main languages are found.
                        all_subtitles = provider_pool.list_subtitles(
                            video, entry_languages | alternative_languages
                        )
                        try:
                            subtitles = provider_pool.download_best_subtitles(
                                all_subtitles,
                                video,
                                entry_languages,
                                min_score=msc,
                                hearing_impaired=hearing_impaired,
                            )
                        except TypeError as e:
                            logger.error(
                                'Downloading subtitles failed due to a bug in subliminal. Please seehttps://github.com/Diaoul/subliminal/issues/921. Error: {}',
                                e,
                            )
                            subtitles = []
                        if subtitles:
                            downloaded_subtitles[video].extend(subtitles)
                            logger.info('Subtitles found for {}', entry['location'])
                        else:
                            # only try to download for alternatives that aren't already downloaded
                            subtitles = provider_pool.download_best_subtitles(
                                all_subtitles,
                                video,
                                alternative_languages,
                                min_score=msc,
                                hearing_impaired=hearing_impaired,
                            )

                            if subtitles:
                                downloaded_subtitles[video].extend(subtitles)
                                entry.reject('subtitles found for a second-choice language.')
                            else:
                                entry.reject('cannot find any subtitles for now.')

                        downloaded_languages = set(
                            [Language.fromietf(str(l.language)) for l in subtitles]
                        )
                        if entry_languages:
                            entry['subtitles_missing'] = entry_languages - downloaded_languages
                            if len(entry['subtitles_missing']) > 0:
                                entry.reject('Subtitles for all primary languages not found')
                except ValueError as e:
                    logger.error('subliminal error: {}', e)
                    entry.fail()

        if downloaded_subtitles:
            if task.options.test:
                logger.verbose('Test mode. Found subtitles:')
            # save subtitles to disk
            for video, subtitle in downloaded_subtitles.items():
                if subtitle:
                    _directory = config.get('directory')
                    if _directory:
                        _directory = os.path.expanduser(_directory)
                    if task.options.test:
                        logger.verbose(
                            '     FOUND LANGUAGES {} for {}',
                            [str(l.language) for l in subtitle],
                            video.name,
                        )
                        continue
                    save_subtitles(video, subtitle, single=single_mode, directory=_directory)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubliminal, 'subliminal', api_ver=2)
