import logging
from flexget.plugin import plugins
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

    def __init__(self):
        self.priorities = {}

    def on_feed_start(self, feed):
        self.priorities = {}
        names = []
        for name, priority in feed.config.get('priority', {}).iteritems():
            names.append(name)
            # abort if no priorities
            if not 'priorities' in plugins[name]:
                log.error('Unable to set plugin %s priority, no default value in plugin' % name)
                continue
            
            # if multiple events with different priorities, abort ..
            # not implemented, would make configuration really messy?
            if len(plugins[name].priorities) > 1:
                log.error('Cannot modify plugin %s priority because of multiple events with default priorities' % name)
                continue
            
            # store original values
            self.priorities[name] = plugins[name].priorities.copy()
            
            # modify original values
            for event in plugins[name].priorities.iterkeys():
                plugins[name].priorities[event] = priority

        log.debug('Changed priority for: %s' % ', '.join(names))
    
    def on_feed_exit(self, feed):
        names = []
        for name, original in self.priorities.iteritems():
            plugins[name].priorities = original
            names.append(name)
        log.debug('Restored priority for: %s' % ', '.join(names))

    on_feed_abort = on_feed_exit

register_plugin(PluginPriority, 'priority')
