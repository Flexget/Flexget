from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='disable')


def all_builtins():
    """Helper function to return an iterator over all builtin plugins."""
    return (p for p in plugin.plugins.values() if p.builtin)


class DisablePlugin:
    """
    Allows disabling built-ins, or plugins referenced by template/include plugin.

    Example::

      templates:
        movies:
          download: ~/torrents/movies/
          .
          .

      tasks:
        nzbs:
          template: movies
          disable:
            - download
          sabnzbd:
            .
            .

      # Task nzbs uses all other configuration from template movies but removes the download plugin
    """

    schema = one_or_more({'type': 'string'})
    disabled_builtins = None

    @plugin.priority(254)
    def on_task_start(self, task, config):
        self.disabled_builtins = []
        disabled = []

        if isinstance(config, str):
            config = [config]

        for p in config:
            # Disable plugins explicitly included in config.
            if p in task.config:
                disabled.append(p)
                del task.config[p]
            # Disable built-in plugins.
            if p in plugin.plugins and plugin.plugins[p].builtin:
                plugin.plugins[p].builtin = False
                self.disabled_builtins.append(p)

        # Disable all builtins mode.
        if 'builtins' in config:
            for p in all_builtins():
                p.builtin = False
                self.disabled_builtins.append(p.name)

        if self.disabled_builtins:
            logger.debug('Disabled built-in plugin(s): {}', ', '.join(self.disabled_builtins))
        if disabled:
            logger.debug('Disabled plugin(s): {}', ', '.join(disabled))

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_exit(self, task, config):
        if not self.disabled_builtins:
            return

        for name in self.disabled_builtins:
            plugin.plugins[name].builtin = True
        logger.debug('Re-enabled builtin plugin(s): {}', ', '.join(self.disabled_builtins))
        self.disabled_builtins = []

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(DisablePlugin, 'disable', api_ver=2)
