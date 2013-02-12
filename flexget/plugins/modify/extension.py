from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('extension')


class ModifyExtension(object):

    """
        Allows specifying file extension explicitly when all other built-in detection mechanisms fail.

        Example:

        extension: nzb
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        root.accept('number')
        return root

    def on_task_modify(self, task):
        ext = task.config.get('extension')
        if ext.startswith('.'):
            ext = ext[1:]

        for entry in task.entries:
            log.debug('`%s` filename is `%s`' % (entry['title'], entry.get('filename', 'N/A')))
            entry['filename'] = '%s.%s' % (entry.get('filename', entry['title']), ext)
            log.debug('filename is now `%s`' % entry['filename'])

register_plugin(ModifyExtension, 'extension')
