import logging
import os
import sys
import tempfile

from flexget import plugin
from flexget.event import event

log = logging.getLogger('subtitles')


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
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
            'exact_match': {'type': 'boolean', 'default': True},
        },
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
                languages: List of languages (3-letter ISO-639-3 code) in order of preference. At least one is required.
                alternatives: List of second-choice languages; subs will be downloaded but entries rejected.
                exact_match: Use file hash only to search for subs, otherwise Subliminal will try to guess by filename.
        """
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        from babelfish import Language
        from dogpile.cache.exception import RegionAlreadyConfigured
        import subliminal
        try:
            subliminal.cache_region.configure('dogpile.cache.dbm', 
                arguments={'filename': os.path.join(tempfile.gettempdir(), 'cachefile.dbm'), 
                           'lock_factory': subliminal.MutexLock})
        except RegionAlreadyConfigured:
            pass
        logging.getLogger("subliminal").setLevel(logging.CRITICAL)
        logging.getLogger("enzyme").setLevel(logging.WARNING)
        langs = set([Language(s) for s in config['languages']])
        alts = set([Language(s) for s in config.get('alternatives', [])])
        for entry in task.accepted:
            if not 'location' in entry:
                log.warning('Cannot act on entries that do not represent a local file.')
            elif not os.path.exists(entry['location']):
                entry.fail('file not found: %s' % entry['location'])
            elif not '$RECYCLE.BIN' in entry['location']:  # ignore deleted files in Windows shares
                try:
                    video = subliminal.scan_video(entry['location'])
                    msc = video.scores['hash'] if config['exact_match'] else 0
                    if langs & video.subtitle_languages:
                        continue  # subs for preferred lang(s) already exists
                    elif subliminal.download_best_subtitles([video], langs, min_score=msc):
                        log.info('Subtitles found for %s' % entry['location'])
                    elif alts and (alts - video.subtitle_languages) and \
                        subliminal.download_best_subtitles([video], alts, min_score=msc):
                        entry.fail('subtitles found for a second-choice language.')
                    else:
                        entry.fail('cannot find any subtitles for now.')
                except Exception as err:
                    # don't want to abort the entire task for errors in a  
                    # single video file or for occasional network timeouts
                    if err.args:
                        msg = err.args[0]
                    else:
                        # Subliminal errors don't always have a message, just use the name
                        msg = 'subliminal error: %s' % err.__class__.__name__
                    log.debug(msg)
                    entry.fail(msg)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubliminal, 'subliminal', api_ver=2)
