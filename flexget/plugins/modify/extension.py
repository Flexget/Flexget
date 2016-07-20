from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('extension')


class ModifyExtension(object):
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
            log.debug('`%s` filename is `%s`' % (entry['title'], entry.get('filename', 'N/A')))
            entry['filename'] = '%s.%s' % (entry.get('filename', entry['title']), ext)
            log.debug('filename is now `%s`' % entry['filename'])


@event('plugin.register')
def register_plugin():
    plugin.register(ModifyExtension, 'extension', api_ver=2)
