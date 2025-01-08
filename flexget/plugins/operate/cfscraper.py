from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning

logger = logger.bind(name='cfscraper')


class CFScraper:
    """
    Plugin that enables scraping of cloudflare protected sites, but it doesn't work anymore.

    This plugin is deprecated and slated for removal in FlexGet v3.14.0.
    """

    schema = {
        'type': 'boolean',
        'deprecated': 'cfscraper is deprecated and slated for removal in v3.14.0.',
    }

    @plugin.priority(253)
    def on_task_start(self, task, config):
        logger.warning(
            "The cfscraper plugin is deprecated and slated for removal in FlexGet v3.14.0."
        )
        raise PluginWarning(
            "The cfscraper plugin is deprecated and slated for removal in FlexGet v3.14.0."
        )


@event('plugin.register')
def register_plugin():
    plugin.register(CFScraper, 'cfscraper', api_ver=2)
