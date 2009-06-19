import logging
from flexget.plugin import *

#from validator_pluginset import PluginSetValidator

log = logging.getLogger('set')

class ModifySet:

    """
        Allows adding information to a feed entry for use later.
    
        Example:

        set:
          path: ~/download/path/
    """
    def __init__(self):
        self.keys = {}
            
    def validator(self):
        from flexget import validator
        v = validator.factory('dict')
        v.accept_any_key('text')
        return v

    def register_key(self, key, type='text'):
        """
        plugins can call this method to register set keys as valid
        """
        if key:
            if not key in self.keys:
                self.keys[key]=type
            
    def register_keys(self, keys):
        """
        for easy registration of multiple keys
        """
        for key, value in keys.iteritems():
            self.register_key(key, value)

    def feed_modify(self, feed):
        for entry in feed.accepted:
            self.modify(entry, feed.config['set'])
            
    def modify(self, entry, config):
        """
        this can be called from a plugin to add set values to an entry
        """

        from flexget import validator
        v = validator.factory('dict')
        for key in self.keys:
            v.accept(self.keys[key], key=key)
            
        if not v.validate(config):
            log.info("set parameters are invalid, error follows")
            log.info(v.errors.messages)
            return
        log.debug('adding set: info to entry:"%s" %s' % (entry['title'], config))
        for key, value in config.iteritems():
            entry[key] = value

register_plugin(ModifySet, 'set')
