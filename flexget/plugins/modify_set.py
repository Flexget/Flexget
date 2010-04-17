import logging
from flexget.plugin import *
import copy

log = logging.getLogger('set')


class ModifySet(object):

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
        v.accept_any_key('any')
        return v

    def register_key(self, key, type='text'):
        """
        plugins can call this method to register set keys as valid
        """
        if key:
            if not key in self.keys:
                self.keys[key] = type
            
    def register_keys(self, keys):
        """
        for easy registration of multiple keys
        """
        for key, value in keys.iteritems():
            self.register_key(key, value)

    @priority(-255)
    def on_feed_filter(self, feed):
        """
        Adds the set dict to all accepted entries. This is not really a filter plugin,
        but it needs to be run before feed_download, so it is run last in the filter chain.
        """
        for entry in feed.accepted:
            self.modify(entry, feed.config['set'], False)
            
    def modify(self, entry, config, validate=True):
        """
        this can be called from a plugin to add set values to an entry
        """
        #create a new dict so we don't overwrite the set config with string replaced values.
        conf = {}
        #loop through config copying items into conf, and doing string replacement where necessary
        for key, value in config.iteritems():
            if isinstance(value, basestring):
                try:
                    conf[key] = value % entry
                except KeyError, e:
                    log.error("Could not set '%s' for %s: does not contain the field '%s.'" % (key, entry['title'], e))
            else:
                conf[key] = value
        
        if validate:
            from flexget import validator
            v = validator.factory('dict')
            for key in self.keys:
                v.accept(self.keys[key], key=key)

            if not v.validate(config):
                log.info('set parameters are invalid, error follows')
                log.info(v.errors.messages)
                return

        log.debug('adding set: info to entry:"%s" %s' % (entry['title'], config))
        
        entry.update(conf)

#filter priority is -255 so we run after all filters are finished
register_plugin(ModifySet, 'set')
