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
        disabled = set()

        if isinstance(config, str):
            config = [config]

        # Disable plugins explicitly included in config.
        for p in config:
            if p == 'builtins':
                continue
            try:
                task.disable_plugin(p)
            except ValueError:
                logger.error('Unknown plugin `{}`', p)
            else:
                disabled.add(p)

        # Disable all builtins mode.
        if 'builtins' in config:
            for p in all_builtins():
                task.disable_plugin(p.name)
                disabled.add(p.name)

        logger.debug('Disabled plugins: {}', ', '.join(disabled))


@event('plugin.register')
def register_plugin():
    plugin.register(DisablePlugin, 'disable', api_ver=2)
