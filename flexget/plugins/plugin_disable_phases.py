import logging
from flexget.plugin import register_plugin

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
        root.accept('text')
        return root

    def on_feed_start(self, feed, config):
        map(feed.disable_phase, config)
                
register_plugin(PluginDisablePhases, 'disable_phases', api_ver=2)
