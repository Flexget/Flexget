import logging
from flexget import plugin
  
log = logging.getLogger('builtins')

class PluginDisableBuiltins:
    """
        Disables all builtin plugins from a feed.
    """
    def __init__(self):
        self.disabled = []

    def validator(self):
        from flexget import validator
        # TODO: accept only list (of texts) or boolean
        return validator.factory('any')
    
    def debug(self):
        for name, info in plugin.plugins.iteritems():
            if not info.builtin:
                continue
            log.debug('Builtin plugin: %s' % (name))
        
    def on_feed_start(self, feed):
        for name, info in plugin.plugins.iteritems():
            if info.builtin:
                if isinstance(feed.config['disable_builtins'], list):
                    if info.name in feed.config['disable_builtins']:
                        info.builtin = False
                        self.disabled.append(name)
                else: 
                    # disabling all builtins
                    info.builtin = False
                    self.disabled.append(name)
        log.debug('Disabled builtin plugin %s' % ', '.join(self.disabled))
        
    def on_feed_exit(self, feed):
        names = []
        for name in self.disabled:
            names.append(name)
            plugin.plugins[name].builtin = True
        self.disabled = []
        log.debug('Enabled builtin plugins %s' % ', '.join(names))
        
    on_feed_abort = on_feed_exit

plugin.register_plugin(PluginDisableBuiltins, 'disable_builtins')
