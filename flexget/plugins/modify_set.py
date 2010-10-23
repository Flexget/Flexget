import logging
from flexget.plugin import register_plugin, priority
import copy
from flexget.utils.tools import replace_from_entry

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

    # Filter priority is -255 so we run after all filters are finished
    @priority(-255)
    def on_feed_filter(self, feed):
        """
        Adds the set dict to all accepted entries. This is not really a filter plugin,
        but it needs to be run before feed_download, so it is run last in the filter chain.
        """
        for entry in feed.entries + feed.rejected:
            self.modify(entry, feed.config['set'], False, entry in feed.accepted)

    def modify(self, entry, config, validate=True, errors=True):
        """
        this can be called from a plugin to add set values to an entry
        """
        # Create a new dict so we don't overwrite the set config with string replaced values.
        conf = {}
        # Loop through config copying items into conf, and doing string replacement where necessary.
        for key, value in config.iteritems():
            if isinstance(value, basestring):
                logger = log.error if errors else log.debug
                conf[key] = replace_from_entry(value, entry, key, logger)
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

        # If there are valid items in the config, apply to entry.
        if conf:
            log.debug('adding set: info to entry:\'%s\' %s' % (entry['title'], conf))
            entry.update(conf)

register_plugin(ModifySet, 'set')
