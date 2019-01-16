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

    @plugin.priority(254)
    def on_task_start(self, task, config):
        if isinstance(config, str):
            config = [config]

        for p in config:
            task.disable_plugin(p)

        # Disable all builtins mode.
        if 'builtins' in config:
            for p in all_builtins():
                task.disable_plugin(p.name)

        if task.disabled_plugins:
            log.debug('Disabled plugin(s): %s' % ', '.join(task.disabled_plugins))


@event('plugin.register')
def register_plugin():
    plugin.register(DisablePlugin, 'disable', api_ver=2)
