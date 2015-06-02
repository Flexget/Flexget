import logging
import os
import tempfile

from flexget import plugin
from flexget.event import event

log = logging.getLogger('subtitles')


class PluginPeriscope(object):
    """
    Search and download subtitles using Periscope by Patrick Dessalle 
    (http://code.google.com/p/periscope/).
    
    Example (complete task)::

      subs:
        find:
          path: 
            - d:\media\incoming
          regexp: '.*\.(avi|mkv|mp4)$'
          recursive: yes
        accept_all: yes
        periscope:
          languages:
            - it
          alternatives:
            - en
          overwrite: yes
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
            'overwrite': {'type': 'boolean', 'default': False},
            'subexts': {'type': 'array', 'items': {'type': 'string'}, 'default': ['srt', 'stp', 'sub', 'stl', 'ssa']},
        },
        'additionalProperties': False
    }

    def on_task_start(self, task, config):
        try:
            import periscope
        except ImportError as e:
            log.debug('Error importing Periscope: %s' % e)
            raise plugin.DependencyError('periscope', 'periscope', 
                                  'Periscope module required. ImportError: %s' % e)
    
    def subbed(self, filename):
        for ext in self.exts:
            if os.path.exists(os.path.splitext(filename)[0] + ext):
                return True
        return False
    
    def on_task_output(self, task, config):
        """
        Configuration::
            periscope:
                languages: List of languages in order of preference (at least one is required).
                alternatives: List of second-choice languages; subs will be downloaded but entries rejected.
                overwrite: If yes it will try to download even for videos that are already subbed. Default: no.
                subexts: List of subtitles file extensions to check (only useful with overwrite=no). 
                    Default: srt, stp, sub, stl, ssa.
        """
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        import periscope
        psc = periscope.Periscope(tempfile.gettempdir())
        logging.getLogger('periscope').setLevel(logging.CRITICAL)  # LOT of messages otherwise
        langs = [s.encode('utf8') for s in config['languages']]  # avoid unicode warnings
        alts = [s.encode('utf8') for s in config.get('alternatives', [])]
        if not config['overwrite']:
            self.exts = ['.' + s for s in config['subexts']]
        for entry in task.accepted:
            if 'location' not in entry:
                log.warning('Cannot act on entries that do not represent a local file.')
            elif not os.path.exists(entry['location']):
                entry.fail('file not found: %s' % entry['location'])
            elif '$RECYCLE.BIN' in entry['location']:
                continue  # ignore deleted files in Windows shares
            elif not config['overwrite'] and self.subbed(entry['location']):
                log.warning('cannot overwrite existing subs for %s' % entry['location'])
            else:
                try:
                    if psc.downloadSubtitle(entry['location'].encode("utf8"), langs):
                        log.info('Subtitles found for %s' % entry['location'])
                    elif alts and psc.downloadSubtitle(entry['location'].encode('utf8'), alts):
                        entry.fail('subtitles found for a second-choice language.')
                    else:
                        entry.fail('cannot find any subtitles for now.')
                except Exception as err:
                    # don't want to abort the entire task for errors in a  
                    # single video file or for occasional network timeouts
                    entry.fail(err.message)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPeriscope, 'periscope', api_ver=2)
