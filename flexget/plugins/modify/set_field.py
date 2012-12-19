from copy import copy
import logging
from flexget.plugin import register_plugin, priority
from flexget.utils.template import RenderError

log = logging.getLogger('set')


class ModifySet(object):

    """Allows adding information to a task entry for use later.

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

    def on_task_start(self, task, config):
        """Checks that jinja2 is available"""
        if not self.jinja:
            log.warning("jinja2 module is not available, set plugin will only work with python string replacement.")

    # Filter priority is -255 so we run after all filters are finished
    @priority(-255)
    def on_task_filter(self, task, config):
        """Adds the set dict to all accepted entries."""
        for entry in task.entries:
            self.modify(entry, config, errors=entry in task.accepted)

    def modify(self, entry, config, errors=True):
        """This can be called from a plugin to add set values to an entry"""

        # Create a new dict so we don't overwrite the set config with string replaced values.
        conf = copy(config)

        # Do jinja2 rendering/string replacement
        for field, value in conf.items():
            if isinstance(value, basestring):
                logger = log.error if errors else log.debug
                try:
                    conf[field] = entry.render(value)
                except RenderError as e:
                    logger('Could not set %s for %s: %s' % (field, entry['title'], e))
                    # If the replacement failed, remove this key from the update dict
                    del conf[field]

        # If there are valid items in the config, apply to entry.
        if conf:
            log.debug('adding set: info to entry:\'%s\' %s' % (entry['title'], conf))
            entry.update(conf)

register_plugin(ModifySet, 'set', api_ver=2)
