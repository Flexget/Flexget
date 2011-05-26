import logging
from flexget import plugin
from flexget.plugin import priority, register_plugin, plugins

log = logging.getLogger('builtins')


def all_builtins():
    """Helper function to return an iterator over all builtin plugins."""
    return (plugin for plugin in plugins.itervalues() if plugin.builtin)


class PluginDisableBuiltins(object):
    """Disables all (or specific) builtin plugins from a feed."""

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        root.accept('list').accept('choice').accept_choices(plugin.name for plugin in all_builtins())
        return root

    def debug(self):
        log.debug('Builtin plugins: %s' % ', '.join(plugin.name for plugin in all_builtins()))

    @priority(255)
    def on_feed_start(self, feed, config):
        self.disabled = []
        if not config:
            return

        for plugin in all_builtins():
            if config is True or plugin.name in config:
                plugin.builtin = False
                self.disabled.append(plugin.name)
        log.debug('Disabled builtin plugin(s): %s' % ', '.join(self.disabled))

    @priority(-255)
    def on_feed_exit(self, feed, config):
        if not self.disabled:
            return

        for name in self.disabled:
            plugin.plugins[name].builtin = True
        log.debug('Enabled builtin plugin(s): %s' % ', '.join(self.disabled))
        self.disabled = []

    on_feed_abort = on_feed_exit

register_plugin(PluginDisableBuiltins, 'disable_builtins', api_ver=2)
