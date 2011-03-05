import logging
from flexget.plugin import register_plugin, feed_phases

log = logging.getLogger('disable_phases')


class PluginDisablePhases(object):
    """Disables phases from feed execution.

    Mainly meant for advanced users and development.

    Example:

    disable_phases:
      - download
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('list')
        root.accept('choice').accept_choices(feed_phases)
        return root

    def on_feed_start(self, feed, config):
        map(feed.disable_phase, config)

register_plugin(PluginDisablePhases, 'disable_phases', api_ver=2)
