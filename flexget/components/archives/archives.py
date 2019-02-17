from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.components.archives import utils

log = logging.getLogger('archives')


class FilterArchives(object):
    """
    Accepts entries that are valid Zip or RAR archives

    This plugin requires the rarfile Python module and unrar command line utility to handle RAR
    archives.

    Configuration:

    unrar_tool: Specifies the path of the unrar tool. Only necessary if its location is not
                defined in the operating system's PATH environment variable.
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {'unrar_tool': {'type': 'string'}},
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        """
        Prepare config for processing
        """
        if not isinstance(config, dict):
            config = {}
        config.setdefault('unrar_tool', '')
        return config

    @plugin.priority(200)
    def on_task_filter(self, task, config):
        """
        Task handler for archives
        """
        if isinstance(config, bool) and not config:
            return

        config = self.prepare_config(config)
        utils.rarfile_set_tool_path(config)

        for entry in task.entries:
            archive_path = entry.get('location', '')

            if utils.is_archive(archive_path):
                entry.accept()
            else:
                entry.reject()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterArchives, 'archives', api_ver=2)
