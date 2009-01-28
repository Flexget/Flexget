import logging

__pychecker__ = 'unusednames=parser,feed'
  
log = logging.getLogger('disable_builtins')

class ModuleDisableBuiltins:
    """
        Disables all builtin modules from a feed.
    """
    
    def register(self, manager, parser):
        manager.register('disable_builtins')
        self.disabled = []
        
    def validate(self, config):
        return []
        
    def feed_start(self, feed):
        for name, module in feed.manager.modules.iteritems():
            if module['builtin']:
                log.debug('Disabling builtin module %s' % name)
                module['builtin'] = False
                self.disabled.append(name)
        
    def feed_exit(self, feed):
        for name in self.disabled:
            log.debug('Enabling builtin module %s' % name)
            feed.manager.modules[name]['builtin'] = True
        self.disabled = []