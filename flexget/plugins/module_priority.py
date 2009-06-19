import logging
from flexget import plugin
from flexget.plugin import *

log = logging.getLogger('priority')

class PluginPriority:

    """
        Allows modifying plugin priorities from default values.
        
        Example:
        
        priority:
          ignore: 50
          series: 100
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept_any_key('number')
        return config

    def feed_start(self, feed):
        self.priorities = {}
        for name, priority in feed.config.get('priority', {}).iteritems():
            # abort if no priorities
            if not 'priorities' in plugin.plugins[name]:
                log.error('Unable to set plugin %s priority, no default value in plugin' % name)
                continue
            
            # if multiple events with different priorities, abort .. not implemented, would make configuration really messy?
            if len(plugin.plugins[name].priorities)>1:
                log.error('Cannot modify plugin %s priority because of multiple events with default priorities' % name)
                continue
            
            # store original values
            self.priorities[name] = plugin.plugins[name].priorities.copy()
            
            # modify original values
            for event, value in plugin.plugins[name].priorities.iteritems():
                plugin.plugins[name].priorities[event] = priority
    
    def feed_exit(self, feed):
        for name, original in self.priorities.iteritems():
            plugin.plugins[name].priorities = original

register_plugin(PluginPriority, 'priority')
