from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.utils.template import render_from_entry, RenderError

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
                    'link_type': {'type': 'string', 'enum': ['soft', 'hard']},
                },
                'required': ['to'],
                'additionalProperties': False,
            },
            {'title': 'specify path', 'type': 'string', 'format': 'path'},
        ]
    }

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'to': config}

        config.setdefault('existing', 'fail')
        config.setdefault('link_type', 'soft')

        return config

    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)
        existing = config['existing']
        for entry in task.accepted:
            if 'location' not in entry:
                entry.fail('Does not have location field for symlinking')
                continue
            lnkfrom = entry['location']
            name = os.path.basename(lnkfrom)
            lnkto = os.path.join(config['to'], name)
            try:
                lnkto = render_from_entry(lnkto, entry)
            except RenderError as error:
                log.error('Could not render path: %s', lnkto)
                entry.fail(str(error))
                return
            # Hardlinks for dirs will not be failed here
            if os.path.exists(lnkto) and (
                config['link_type'] == 'soft' or os.path.isfile(lnkfrom)
            ):
                msg = 'Symlink destination %s already exists' % lnkto
                if existing == 'ignore':
                    log.verbose(msg)
                else:
                    entry.fail(msg)
                continue
            log.verbose('%slink `%s` to `%s`', config['link_type'], lnkfrom, lnkto)
            try:
                if config['link_type'] == 'soft':
                    os.symlink(lnkfrom, lnkto)
                else:
                    if os.path.isdir(lnkfrom):
                        self.hard_link_dir(lnkfrom, lnkto, existing)
                    else:
                        dirname = os.path.dirname(lnkto)
                        if not os.path.exists(dirname):
                            os.makedirs(dirname)
                        os.link(lnkfrom, lnkto)
            except OSError as e:
                entry.fail('Failed to create %slink, %s' % (config['link_type'], e))

    def hard_link_dir(self, path, destination, existing):
        if not os.path.exists(destination):
            try:
                os.makedirs(destination)
            except OSError as e:
                # Raised when it already exists, but are there other cases?
                log.debug('Failed to create destination dir %s: %s', destination, e)
        # 'recursively' traverse and hard link
        working_dir = os.getcwd()
        os.chdir(path)  # change working dir to make dir joins easier
        for root, dirs, files in os.walk('.'):
            dst_dir = os.path.abspath(os.path.join(destination, root))
            for d in dirs:
                try:
                    os.mkdir(d)
                except OSError as e:
                    # Raised when it already exists, but are there other cases?
                    log.debug('Failed to create subdir %s: %s', d, e)
            for f in files:
                src_file = os.path.join(root, f)
                dst_file = os.path.join(dst_dir, f)
                log.debug('Hardlinking %s to %s', src_file, dst_file)
                try:
                    os.link(src_file, dst_file)
                except OSError as e:
                    log.debug('Failed to create hardlink for file %s: %s', f, e)
                    if existing == 'fail':
                        raise  # reraise to fail the entry in the calling function

        os.chdir(working_dir)


@event('plugin.register')
def register_plugin():
    if os.name == 'nt':
        log.trace('Symlinks not supported on Windows. Skipping Symlink plugin register.')
        return
    plugin.register(Symlink, 'symlink', api_ver=2)
