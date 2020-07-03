import platform
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='exists')


class FilterExists:
    """
        Reject entries that already exist in given path.

        Example::

          exists: /storage/movies/
    """

    schema = one_or_more({'type': 'string', 'format': 'path'})

    def prepare_config(self, config):
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, str):
            config = [config]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            logger.debug('No accepted entries, not scanning for existing.')
            return
        logger.verbose('Scanning path(s) for existing files.')
        config = self.prepare_config(config)
        filenames = {}
        for folder in config:
            folder = Path(folder).expanduser()
            if not folder.exists():
                raise plugin.PluginWarning('Path %s does not exist' % folder, logger)
            for p in folder.rglob('*'):
                if p.is_file():
                    key = p.name
                    # windows file system is not case sensitive
                    if platform.system() == 'Windows':
                        key = key.lower()
                    filenames[key] = p
        for entry in task.accepted:
            # priority is: filename, location (filename only), title
            name = Path(entry.get('filename', entry.get('location', entry['title']))).name
            if platform.system() == 'Windows':
                name = name.lower()
            if name in filenames:
                logger.debug('Found {} in {}', name, filenames[name])
                entry.reject('exists in %s' % filenames[name])


@event('plugin.register')
def register_plugin():
    plugin.register(FilterExists, 'exists', api_ver=2)
