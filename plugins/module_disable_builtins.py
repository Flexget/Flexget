import logging
  
log = logging.getLogger('disable_builtins')

class PluginDisableBuiltins:
    """
        Disables all builtin plugins from a feed.
    """
    
    def register(self, manager, parser):
        manager.register('disable_builtins')
        self.disabled = []
        
    def validator(self):
        import validator
        return validator.factory('any')
        
    def feed_start(self, feed):
        for name, plugin in feed.manager.plugins.iteritems():
            if plugin['builtin']:
                if isinstance(feed.config['disable_builtins'], list):
                    if plugin['name'] in feed.config['disable_builtins']:
                        plugin['builtin'] = False
                        self.disabled.append(name)
                else: #disabling all builtins
                    log.debug('Disabling builtin plugin %s' % name)
                    plugin['builtin'] = False
                    self.disabled.append(name)
        
    def feed_exit(self, feed):
        for name in self.disabled:
            log.debug('Enabling builtin plugin %s' % name)
            feed.manager.plugins[name]['builtin'] = True
        self.disabled = []
