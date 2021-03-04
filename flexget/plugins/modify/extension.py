from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='extension')


class ModifyExtension:
    """
    Allows specifying file extension explicitly when all other built-in detection mechanisms fail.

    Example:

    extension: nzb
    """

    schema = {'type': ['string', 'number']}

    def on_task_modify(self, task, config):
        ext = str(config)
        if ext.startswith('.'):
            ext = ext[1:]

        for entry in task.entries:
            logger.debug('`{}` filename is `{}`', entry['title'], entry.get('filename', 'N/A'))
            entry['filename'] = '%s.%s' % (entry.get('filename', entry['title']), ext)
            logger.debug('filename is now `{}`', entry['filename'])


@event('plugin.register')
def register_plugin():
    plugin.register(ModifyExtension, 'extension', api_ver=2)
