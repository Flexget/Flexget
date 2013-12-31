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
            - en
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

    def subbed(self, filename, exts):
        for ext in exts:
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
                subexts: List of subtitles file extensions to check (only useful with overwrite=no). Default: srt, stp, sub, stl, ssa.
        """
        import periscope
        psc = periscope.Periscope(tempfile.gettempdir())
        # to avoid A LOT of info/warnings/errors coming from periscope:
        logging.getLogger("periscope").setLevel(logging.CRITICAL)

        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        langs = [s.encode('utf8') for s in config['languages']]  # unicode warnings in periscope
        alts = []
        if 'alternatives' in config:
            alts = [s.encode('utf8') for s in config['alternatives']]
        if not config['overwrite']:
            exts = ['.'+s for s in config['subexts']]
        for entry in task.accepted:
            if not 'location' in entry:
                entry.reject('is not a local file')
                continue
            if '$RECYCLE.BIN' in entry['location']:  # happens in connected network shares
                entry.reject("is in Windows recycle-bin")
            elif not os.path.exists(entry['location']):
                entry.reject('file not found')  # periscope works on hashes
            elif not config['overwrite'] and self.subbed(entry['location'], exts):
                entry.reject('cannot overwrite existing subs')
            elif psc.downloadSubtitle(entry['location'].encode("utf8"), langs):
                log.info('Subtitles found for %s' % entry['location'])
            elif alts and psc.downloadSubtitle(entry['location'].encode("utf8"), alts):
                entry.reject('subtitles found for a second-choice language.')
            else:
                entry.reject('cannot find any subtitles for now.')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginPeriscope, 'periscope', api_ver=2)
