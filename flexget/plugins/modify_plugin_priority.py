import logging
from flexget.plugin import plugins, FEED_EVENTS, EVENT_METHODS
from flexget.plugin import *

log = logging.getLogger('p_priority')


class PluginPriority(object):

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
        for name, priority in feed.config.get('plugin_priority', {}).iteritems():
            names.append(name)
            originals = self.priorities.setdefault(name, {})
            for method in plugins[name].event_handlers.itervalues():
                originals[method.method_name] = method.priority
                log.debug('stored %s original value %s' % (method.name, method.priority))
                
            print originals

        log.debug('Changed priority for: %s' % ', '.join(names))

    def on_feed_exit(self, feed):
        names = []
        for name in feed.config.get('plugin_priority', {}).keys():
            names.append(name)

            """
            from IPython.Shell import IPShellEmbed
            args = []
            ipshell = IPShellEmbed(args)
            ipshell()"""
            
            originals = self.priorities[name]
            for method_name, priority in originals.iteritems():
                plugins[name].event_handlers[method_name].priority = priority
                    
        log.debug('Restored priority for: %s' % ', '.join(names))

    on_feed_abort = on_feed_exit

register_plugin(PluginPriority, 'plugin_priority')
