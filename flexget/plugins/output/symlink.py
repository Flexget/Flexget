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
                    'existing': {'type': 'string', 'enum': ['ignore', 'fail']},
                    'type': {'type': 'string', 'enum': ['soft', 'hard']}
                },
                'required': ['to'],
                'additionalProperties': False
            },
            {'title': 'specify path', 'type': 'string', 'format': 'path'},
        ]
    }

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'to': config}

        config.setdefault('existing', 'fail')
        config.setdefault('type', 'soft')

        return config

    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)
        for entry in task.accepted:
            if 'location' not in entry:
                entry.fail('Does not have location field for symlinking')
                continue
            lnkfrom = entry['location']
            name = os.path.basename(lnkfrom)
            lnkto = os.path.join(config['to'], name)
            if os.path.exists(lnkto):
                msg = 'Symlink destination %s already exists' % lnkto
                if config.get('existing', 'fail') == 'ignore':
                    log.verbose(msg)
                else:
                    entry.fail(msg)
                continue
            log.verbose('%slink `%s` to `%s`', config['type'], lnkfrom, lnkto)
            try:
                if config['type'] == 'soft':
                    os.symlink(lnkfrom, lnkto)
                else:
                    if os.path.isdir(lnkfrom):
                        self.hard_link_dir(lnkfrom, lnkto)
                    else:
                        os.link(lnkfrom, lnkto)
            except OSError as e:
                entry.fail('Failed to create %slink, %s' % (config['type'], e))

    def hard_link_dir(self, path, destination):
        if not os.path.exists(destination):
            try:
                os.mkdir(destination)
            except OSError as e:
                # Raised when it already exists, but are there other cases?
                log.debug('Failed to create destination dir %s: %s', destination, e)
        # 'recursively' traverse and hard link
        for root, dirs, files in os.walk(path):
            dest_dir = os.path.join(destination, root)
            for dir in dirs:
                try:
                    os.mkdir(dir)
                except OSError as e:
                    # Raised when it already exists, but are there other cases?
                    log.debug('Failed to create subdir %s: %s', dir, e)
            for f in files:
                src_file = os.path.join(root, f)
                dst_file = os.path.join(dest_dir, f)
                os.link(src_file, dst_file)


@event('plugin.register')
def register_plugin():
    if os.name != 'posix':
        return
    plugin.register(Symlink, 'symlink', api_ver=2)
