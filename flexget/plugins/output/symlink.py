from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os

from flexget import plugin
from flexget.event import event

log = logging.getLogger('symlink')


class Symlink(object):

    schema = {
        'oneOf': [
            {
                'title': 'specify options',
                'type': 'object',
                'properties': {
                    'to': {'type': 'string', 'format': 'path'},
                    'existing': {'type': 'string', 'enum': ['ignore', 'fail']}
                },
                'additionalProperties': False
            },
            {'title': 'specify path', 'type': 'string', 'format': 'path'},
        ]
    }

    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            if 'location' not in entry:
                entry.fail('Does not have location field for symlinking')
                continue
            lnkfrom = entry['location']
            name = os.path.split(lnkfrom.rstrip('/'))[1]
            lnkto = os.path.join(config['to'], name)
            if os.path.exists(lnkto):
                msg = 'Symlink destination already exists'
                if config.get('existing', 'fail') == 'ignore':
                    log.verbose(msg)
                else:
                    entry.fail(msg)
                continue
            log.verbose('Symlink `%s` to `%s`', lnkfrom, lnkto)
            try:
                os.symlink(lnkfrom, lnkto)
            except OSError as e:
                entry.fail('Failed to create symlink, %s' % e.strerror)


@event('plugin.register')
def register_plugin():
    if os.name != 'posix':
        return
    plugin.register(Symlink, 'symlink', api_ver=2)
