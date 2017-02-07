from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

__name__ = 'list_framework'
log = logging.getLogger(__name__)


class ListFramework(object):
    def __init__(self, plugin_name, plugin_config):
        try:
            self.plugin_name = plugin_name
            self.plugin_config = plugin_config
            self.list = plugin.get_plugin_by_name(plugin_name).instance.get_list(plugin_config)
        except AttributeError:
            raise PluginError('Plugin %s does not support list interface' % plugin_name)
        if self.list.immutable:
            raise PluginError(self.list.immutable)

    def add(self, entries):
        log.verbose('adding entries from %s - %s', self.plugin_name, self.plugin_config)
        self.list |= entries

    def remove(self, entries):
        log.verbose('removing entries from %s - %s', self.plugin_name, self.plugin_config)
        self.list -= entries

    def clear(self):
        log.verbose('clearing all items from %s - %s', self.plugin_name, self.plugin_config)
        self.list.clear()


@event('plugin.register')
def register_plugin():
    plugin.register(ListFramework, __name__, api_ver=2, interfaces=[])
