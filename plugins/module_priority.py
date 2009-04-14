import logging
from manager import PluginWarning



log = logging.getLogger('priority')

class PluginPriority:

    """
        Allows modifying plugin priorities from default values.
        
        Example:
        
        priority:
          ignore: 50
          series: 100
    """

    def register(self, manager, parser):
        manager.register('priority')
        
    def validator(self):
        import validator
        config = validator.factory('dict')
        config.accept_any_key('number')
        return config

    def feed_start(self, feed):
        self.priorities = {}
        for plugin, priority in feed.config.get('priority', {}).iteritems():
            # abort if no priorities
            if not 'priorities' in feed.manager.plugins[plugin]:
                log.error('Unable to set plugin %s priority, no default value in plugin' % plugin)
                continue
            
            # if multiple events with different priorities, abort .. not implemented, would make configuration really messy?
            if len(feed.manager.plugins[plugin]['priorities'])>1:
                log.error('Cannot modify plugin %s priority because of multiple events with default priorities' % plugin)
                continue
            
            # store original values
            self.priorities[plugin] = feed.manager.plugins[plugin]['priorities'].copy()
            
            # modify original values
            for event, value in feed.manager.plugins[plugin]['priorities'].iteritems():
                feed.manager.plugins[plugin]['priorities'][event] = priority
    
    def feed_exit(self, feed):
        for plugin, original in self.priorities.iteritems():
            feed.manager.plugins[plugin]['priorities'] = original