import logging
import os
import tempfile

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='subtitles')


class PluginPeriscope:
    r"""Search and download subtitles using Periscope by Patrick Dessalle (http://code.google.com/p/periscope/).

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
            'subexts': {
                'type': 'array',
                'items': {'type': 'string'},
                'default': ['srt', 'stp', 'sub', 'stl', 'ssa'],
            },
        },
        'additionalProperties': False,
    }

    def on_task_start(self, task, config):
        try:
            import periscope  # noqa: F401
        except ImportError as e:
            logger.debug('Error importing Periscope: {}', e)
            raise plugin.DependencyError(
                'periscope', 'periscope', f'Periscope module required. ImportError: {e}'
            )

    def subbed(self, filename):
        return any(os.path.exists(os.path.splitext(filename)[0] + ext) for ext in self.exts)

    def on_task_output(self, task, config):
        """Register this as an output plugin.

        Configuration::

            periscope:
                languages: List of languages in order of preference (at least one is required).
                alternatives: List of second-choice languages; subs will be downloaded but entries rejected.
                overwrite: If yes it will try to download even for videos that are already subbed. Default: no.
                subexts: List of subtitles file extensions to check (only useful with overwrite=no).
                    Default: srt, stp, sub, stl, ssa.
        """
        if not task.accepted:
            logger.debug('nothing accepted, aborting')
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
                logger.warning('Cannot act on entries that do not represent a local file.')
            elif not entry['location'].exists():
                entry.fail('file not found: {}'.format(entry['location']))
            elif '$RECYCLE.BIN' in str(entry['location']):
                continue  # ignore deleted files in Windows shares
            elif not config['overwrite'] and self.subbed(entry['location']):
                logger.warning('cannot overwrite existing subs for {}', entry['location'])
            else:
                try:
                    if psc.downloadSubtitle(str(entry['location']).encode('utf8'), langs):
                        logger.info('Subtitles found for {}', entry['location'])
                    elif alts and psc.downloadSubtitle(
                        str(entry['location']).encode('utf8'), alts
                    ):
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
