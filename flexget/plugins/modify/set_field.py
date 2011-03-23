from copy import copy
import logging
from flexget.plugin import register_plugin, priority
from flexget.utils.tools import replace_from_entry

log = logging.getLogger('set')
jinja = False


class ModifySet(object):

    """
        Allows adding information to a feed entry for use later.

        Example:

        set:
          path: ~/download/path/
    """

    def __init__(self):
        self.keys = {}
        try:
            from jinja2 import Environment
        except ImportError:
            self.jinja = False
        else:
            self.jinja = True

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

    def on_feed_start(self, feed, config):
        """Checks that jinja2 is available"""
        if not self.jinja:
            log.warning("jinja2 module is not available, set plugin will only work with python string replacement.")

    # Filter priority is -255 so we run after all filters are finished
    @priority(-255)
    def on_feed_filter(self, feed, config):
        """
        Adds the set dict to all accepted entries. This is not really a filter plugin,
        but it needs to be run before feed_download, so it is run last in the filter chain.
        """
        for entry in feed.entries + feed.rejected:
            self.modify(entry, config, False, entry in feed.accepted)

    def modify(self, entry, config, validate=False, errors=True):
        """
        this can be called from a plugin to add set values to an entry
        """
        # Create a new dict so we don't overwrite the set config with string replaced values.
        conf = copy(config)

        # If jinja2 is available do template replacement
        if self.jinja:
            from jinja2 import Environment, StrictUndefined, UndefinedError
            env = Environment(undefined=StrictUndefined)
            for field, template_string in conf.iteritems():
                if isinstance(template_string, basestring):
                    template = env.from_string(template_string)
                    try:
                        result = template.render(entry)
                    except UndefinedError:
                        result = ''
                    conf[field] = result

        # Do string replacement
        for field, value in conf.iteritems():
            if isinstance(value, basestring):
                logger = log.error if errors else log.debug
                conf[field] = replace_from_entry(value, entry, field, logger)

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

register_plugin(ModifySet, 'set', api_ver=2)
