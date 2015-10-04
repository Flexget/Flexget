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
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
            'exact_match': {'type': 'boolean', 'default': True},
            'providers': {'type': 'array', 'items': {'type': 'string', 'enum': PROVIDERS}},
            'single': {'type': 'boolean', 'default': True},
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
            log.debug('Error importing Babelfish: %s' % e)
            raise plugin.DependencyError('subliminal', 'babelfish', 'Babelfish module required. ImportError: %s' % e)
        try:
            import subliminal
        except ImportError as e:
            log.debug('Error importing Subliminal: %s' % e)
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
        """
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        from babelfish import Language
        from dogpile.cache.exception import RegionAlreadyConfigured
        import subliminal
        from subliminal.cli import MutexLock
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
        langs = set([Language.fromietf(s) for s in config.get('languages', [])])
        alts = set([Language.fromietf(s) for s in config.get('alternatives', [])])
        # keep all downloaded subtitles and save to disk when done (no need to write every time)
        downloaded_subtitles = collections.defaultdict(list)
        providers_list = config.get('providers', None)
        # test if only one language was provided, if so we will download in single mode
        # (aka no language code added to subtitle filename)
        # unless we are forced not to by configuration
        # if we pass 'yes' for single in configuration but choose more than one language
        # we ignore the configuration and add the language code to the
        # potentially downloaded files
        single_mode = config.get('single', '') and len(langs | alts) <= 1
        for entry in task.accepted:
            if 'location' not in entry:
                log.warning('Cannot act on entries that do not represent a local file.')
            elif not os.path.exists(entry['location']):
                entry.fail('file not found: %s' % entry['location'])
            elif '$RECYCLE.BIN' not in entry['location']:  # ignore deleted files in Windows shares
                try:
                    entry_langs = entry.get('subtitle_languages', [])
                    if not entry_langs:
                        entry_langs = langs
                    video = subliminal.scan_video(entry['location'])
                    if isinstance(video, subliminal.Episode):
                        title = video.series
                    else:
                        title = video.title
                    log.info('Name computed for %s was %s' % (entry['location'], title))
                    msc = video.scores['hash'] if config['exact_match'] else 0
                    if entry_langs & video.subtitle_languages:
                        entry['subtitles_missing'] = set()
                        continue  # subs for preferred lang(s) already exists
                    else:
                        subtitle = subliminal.download_best_subtitles([video], entry_langs, providers=providers_list,
                                                                      min_score=msc)
                        if subtitle and any(subtitle.values()):
                            downloaded_subtitles.update(subtitle)
                            log.info('Subtitles found for %s' % entry['location'])
                        else:
                            # TODO check performance hit -- this explicit check may be better on slower devices
                            # but subliminal already handles it for us, but it loops over all providers before stopping
                            remaining_alts = alts - video.subtitle_languages
                            if remaining_alts:
                                # only try to download for alternatives that aren't alread downloaded
                                subtitle = subliminal.download_best_subtitles([video], remaining_alts,
                                                                              providers=providers_list, min_score=msc)
                            # this potentially just checks an already checked assignment bleh
                            if subtitle and any(subtitle.values()):
                                downloaded_subtitles.update(subtitle)
                                entry.fail('subtitles found for a second-choice language.')
                            else:
                                entry.fail('cannot find any subtitles for now.')
                        downloaded_languages = set([Language.fromietf(unicode(l.language))
                                                    for l in subtitle[video]])
                        if entry_langs:
                            entry['subtitles_missing'] = entry_langs - downloaded_languages
                except Exception as err:
                    # don't want to abort the entire task for errors in a  
                    # single video file or for occasional network timeouts
                    if err.args:
                        msg = unicode(err.args[0])
                    else:
                        # Subliminal errors don't always have a message, just use the name
                        msg = 'subliminal error: %s' % err.__class__.__name__
                    log.debug(msg)
                    entry.fail(msg)
        if downloaded_subtitles:
            # save subtitles to disk
            for k, v in downloaded_subtitles.iteritems():
                if v:
                    subliminal.save_subtitles(k, v, single=single_mode)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubliminal, 'subliminal', api_ver=2)
