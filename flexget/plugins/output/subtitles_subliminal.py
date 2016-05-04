from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import collections
import logging
import os
import sys
import tempfile

from flexget import plugin
from flexget.event import event

log = logging.getLogger('subtitles')

PROVIDERS = [
    'opensubtitles',
    'thesubdb',
    'podnapisi',
    'addic7ed',
    'tvsubtitles'
]


class PluginSubliminal(object):
    """
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
          providers: addic7ed, opensubtitles
          single: no
          directory: /disk/subtitles
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
        },
        'required': ['languages'],
        'additionalProperties': False
    }

    def on_task_start(self, task, config):
        if list(sys.version_info) < [2, 7]:
            raise plugin.DependencyError('subliminal', 'Python 2.7', 'Subliminal plugin requires python 2.7.')
        try:
            import babelfish
        except ImportError as e:
            log.debug('Error importing Babelfish: %s', e)
            raise plugin.DependencyError('subliminal', 'babelfish', 'Babelfish module required. ImportError: %s' % e)
        try:
            import subliminal
        except ImportError as e:
            log.debug('Error importing Subliminal: %s', e)
            raise plugin.DependencyError('subliminal', 'subliminal', 'Subliminal module required. ImportError: %s' % e)
    
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
        """
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        from babelfish import Language
        from dogpile.cache.exception import RegionAlreadyConfigured
        import subliminal
        from subliminal.cli import MutexLock
        from subliminal.score import episode_scores, movie_scores
        try:
            subliminal.region.configure('dogpile.cache.dbm',
                                        arguments={
                                            'filename': os.path.join(tempfile.gettempdir(), 'cachefile.dbm'),
                                            'lock_factory': MutexLock,
                                        })
        except RegionAlreadyConfigured:
            pass
        logging.getLogger("subliminal").setLevel(logging.CRITICAL)
        logging.getLogger("enzyme").setLevel(logging.WARNING)
        languages = set([Language.fromietf(s) for s in config.get('languages', [])])
        alternative_languages = set([Language.fromietf(s) for s in config.get('alternatives', [])])
        # keep all downloaded subtitles and save to disk when done (no need to write every time)
        downloaded_subtitles = collections.defaultdict(list)
        providers_list = config.get('providers', None)
        # test if only one language was provided, if so we will download in single mode
        # (aka no language code added to subtitle filename)
        # unless we are forced not to by configuration
        # if we pass 'yes' for single in configuration but choose more than one language
        # we ignore the configuration and add the language code to the
        # potentially downloaded files
        single_mode = config.get('single', '') and len(languages | alternative_languages) <= 1
        for entry in task.accepted:
            if 'location' not in entry:
                log.warning('Cannot act on entries that do not represent a local file.')
            elif not os.path.exists(entry['location']):
                entry.fail('file not found: %s' % entry['location'])
            elif '$RECYCLE.BIN' not in entry['location']:  # ignore deleted files in Windows shares
                try:
                    entry_languages = entry.get('subtitle_languages') or languages

                    video = subliminal.scan_video(entry['location'])
                    existing_subtitles = set(subliminal.core.search_external_subtitles(entry['location']).values())
                    video.subtitle_languages = existing_subtitles
                    if isinstance(video, subliminal.Episode):
                        title = video.series
                        hash_scores = episode_scores['hash']
                    else:
                        title = video.title
                        hash_scores = movie_scores['hash']
                    log.info('Name computed for %s was %s', entry['location'], title)
                    msc = hash_scores if config['exact_match'] else 0
                    if entry_languages & existing_subtitles:
                        log.debug('All preferred languages already exist for "%s"', entry['title'])
                        entry['subtitles_missing'] = set()
                        continue  # subs for preferred lang(s) already exists
                    else:
                        subtitle = subliminal.download_best_subtitles([video], entry_languages,
                                                                      providers=providers_list, min_score=msc)
                        if subtitle and any(subtitle.values()):
                            downloaded_subtitles.update(subtitle)
                            log.info('Subtitles found for %s', entry['location'])
                        else:
                            # only try to download for alternatives that aren't alread downloaded
                            subtitle = subliminal.download_best_subtitles([video], alternative_languages,
                                                                          providers=providers_list, min_score=msc)

                            if subtitle and any(subtitle.values()):
                                downloaded_subtitles.update(subtitle)
                                entry.fail('subtitles found for a second-choice language.')
                            else:
                                entry.fail('cannot find any subtitles for now.')
                        downloaded_languages = set([Language.fromietf(str(l.language))
                                                    for l in subtitle[video]])
                        if entry_languages:
                            entry['subtitles_missing'] = entry_languages - downloaded_languages
                except ValueError as e:
                    log.error('subliminal error: %s', e)
                    entry.fail()

        if downloaded_subtitles:
            # save subtitles to disk
            for video, subtitle in downloaded_subtitles.items():
                if subtitle:
                    _directory = config.get('directory', None)
                    if _directory:
                        _directory = os.path.expanduser(_directory)
                    subliminal.save_subtitles(video, subtitle, single=single_mode, directory=_directory)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubliminal, 'subliminal', api_ver=2)
