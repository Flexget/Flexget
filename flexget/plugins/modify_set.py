import logging
from flexget.plugin import *
import copy

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
        #run string replacement on all string variables before validation
        conf = copy.deepcopy(config)
        conf.update(dict([(key, value % entry) for (key, value) in config.iteritems() if isinstance(value, basestring)]))
        
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
register_plugin(ModifySet, 'set', priorities={'filter': -255})
