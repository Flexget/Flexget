import logging
import os
import tempfile

from flexget.plugin import register_plugin, DependencyError

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
        try:
            import babelfish
        except ImportError as e:
            log.debug('Error importing Babelfish: %s' % e)
            raise DependencyError('subliminal', 'babelfish', 
                                  'Babelfish module required. ImportError: %s' % e)
        try:
            import subliminal
        except ImportError as e:
            log.debug('Error importing Subliminal: %s' % e)
            raise DependencyError('subliminal', 'subliminal', 
                                  'Subliminal module required. ImportError: %s' % e)
    
    def on_task_output(self, task, config):
        """
        Configuration::
            subliminal:
                languages: List of languages (3-letter ISO-639-3 code) in order of preference. At least one is required.
                alternatives: List of second-choice languages; subs will be downloaded but entries rejected.
        """
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        from babelfish import Language
        import subliminal
        subliminal.cache_region.configure('dogpile.cache.dbm', 
            arguments={'filename': os.path.join(tempfile.gettempdir(), 'cachefile.dbm'), 
                       'lock_factory': subliminal.MutexLock})
        logging.getLogger("subliminal").setLevel(logging.WARNING)
        logging.getLogger("enzyme").setLevel(logging.WARNING)
        langs = set([Language(s) for s in config['languages']])
        alts = set([Language(s) for s in config.get('alternatives', [])])
        def getsubs(vd, ln):
            try:
                return subliminal.download_best_subtitles([vd], ln, min_score=vd.scores['hash']) \
                        if config['exact_match'] else subliminal.download_best_subtitles([vd], ln)
            except Exception as err:
                log.error('Subliminal error: %s' % err.message)
                return []
        for entry in task.accepted:
            if not 'location' in entry:
                entry.reject('is not a local file')
            elif '$RECYCLE.BIN' in entry['location']:  # happens in connected network shares
                entry.reject("is in Windows recycle-bin")
            elif not os.path.exists(entry['location']):
                entry.reject('file not found')
            else:
                try:
                    video = subliminal.scan_video(entry['location'])
                except Exception as err:
                    entry.fail('subliminal scan error: %s' % err.message)
                if langs & video.subtitle_languages:
                    continue
                if len(getsubs(video, langs)) > 0:
                    log.info('Subtitles found for %s' % entry['location'])
                elif alts and (alts - video.subtitle_languages) and len(getsubs(video, alts)) > 0:
                    entry.reject('subtitles found for a second-choice language.')
                else:
                    entry.reject('cannot find any subtitles for now.')


register_plugin(PluginSubliminal, 'subliminal', api_ver=2)
