from __future__ import unicode_literals, division, absolute_import
from flexget.entry import Entry
from flexget.plugin import register_plugin


class ExternalPlugin(object):
    def on_task_input(self, task, config):
        return [Entry('test entry', 'fake url')]

register_plugin(ExternalPlugin, 'external_plugin', api_ver=2)
