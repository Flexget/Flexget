from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

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
    disabled_builtins = None

    @plugin.priority(254)
    def on_task_start(self, task, config):
        self.disabled_builtins = []
        disabled = []

        if isinstance(config, basestring):
            config = [config]

        for p in config:
            # Disable plugins explicitly included in config.
            if p in task.config:
                disabled.append(p)
                del (task.config[p])
            # Disable built-in plugins.
            if p in plugin.plugins and plugin.plugins[p].builtin:
                plugin.plugins[p].builtin = False
                self.disabled_builtins.append(p)

        # Disable all builtins mode.
        if 'builtins' in config:
            for p in all_builtins():
                p.builtin = False
                self.disabled_builtins.append(p.name)

        if self.disabled_builtins:
            log.debug('Disabled built-in plugin(s): %s' % ', '.join(self.disabled_builtins))
        if disabled:
            log.debug('Disabled plugin(s): %s' % ', '.join(disabled))

    @plugin.priority(-255)
    def on_task_exit(self, task, config):
        if not self.disabled_builtins:
            return

        for name in self.disabled_builtins:
            plugin.plugins[name].builtin = True
        log.debug('Re-enabled builtin plugin(s): %s' % ', '.join(self.disabled_builtins))
        self.disabled_builtins = []

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(DisablePlugin, 'disable', api_ver=2)
