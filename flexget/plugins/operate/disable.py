from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

log = logging.getLogger('disable')


def all_builtins():
    """Helper function to return an iterator over all builtin plugins."""
    return (p for p in plugin.plugins.values() if p.builtin)


class DisablePlugin(object):
    """
    Allows disabling built-ins, or plugins referenced by template/include plugin.

    Example::

      templates:
        movies:
          download: ~/torrents/movies/
          .
          .

      tasks:
        nzbs:
          template: movies
          disable:
            - download
          sabnzbd:
            .
            .

      # Task nzbs uses all other configuration from template movies but removes the download plugin
    """

    schema = one_or_more({'type': 'string'})
    disabled_plugins = None

    @plugin.priority(254)
    def on_task_start(self, task, config):
        self.disabled_plugins = []
        disabled_in_task = []

        if isinstance(config, str):
            config = [config]

        for p in config:
            # Disable plugins explicitly included in config.
            if p in task.config:
                disabled_in_task.append(p)
                del (task.config[p])
            # Disable built-in plugins.
            if p in plugin.plugins:
                plugin.plugins[p].disabled = True
                self.disabled_plugins.append(p)

        # Disable all builtins mode.
        if 'builtins' in config:
            for p in all_builtins():
                p.disabled = True
                self.disabled_plugins.append(p.name)

        if self.disabled_plugins:
            log.debug('Disabled plugin(s): %s' % ', '.join(self.disabled_plugins))
        if disabled_in_task:
            log.debug('Disabled task plugin(s): %s' % ', '.join(disabled_in_task))

    @plugin.priority(-255)
    def on_task_exit(self, task, config):
        if not self.disabled_plugins:
            return

        for name in self.disabled_plugins:
            plugin.plugins[name].disabled = False
        log.debug('Re-enabled plugin(s): %s' % ', '.join(self.disabled_plugins))
        self.disabled_plugins = []

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(DisablePlugin, 'disable', api_ver=2)
