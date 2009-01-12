import logging
import datetime
from manager import ModuleWarning

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('priority')

class ModulePriority:

    """
        Allows modifying module priorities from default values.
        
        Example:
        
        priority:
          ignore: 50
          series: 100
    """

    def register(self, manager, parser):
        manager.register('priority')
        
    def _validate(self, config):
        from validator import DictValidator
        root = DictValidator() 
        root.accept_any_key(int)
        root.validate(config)
        return root.error.messages
        

    def feed_start(self, feed):
        self.priorities = {}
        for module, priority in feed.config.get('priority', {}).iteritems():
            # abort if no priorities
            if not feed.manager.modules[module].has_key('priorities'):
                log.error('Unable to set module %s priority, no default value in module' % module)
                continue
            
            # if multiple events with different priorities, abort .. not implemented, would make configuration really messy?
            if len(feed.manager.modules[module]['priorities'])>1:
                log.error('Cannot modify module %s priority because of multiple events with default priorities' % module)
                continue
            
            # store original values
            self.priorities[module] = feed.manager.modules[module]['priorities'].copy()
            
            # modify original values
            for event, value in feed.manager.modules[module]['priorities'].iteritems():
                feed.manager.modules[module]['priorities'][event] = priority
    
    def feed_exit(self, feed):
        for module, original in self.priorities.iteritems():
            feed.manager.modules[module]['priorities'] = original