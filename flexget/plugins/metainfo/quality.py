from loguru import logger

from flexget import plugin
from flexget.entry import register_lazy_lookup
from flexget.event import event
from flexget.utils import qualities

logger = logger.bind(name='metainfo_quality')


class MetainfoQuality:
    """
    Utility:

    Set quality attribute for entries.
    """

    schema = {'type': 'boolean'}

    @plugin.priority(127)  # Run after other plugins that might fill quality (series)
    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if config is False:
            return
        for entry in task.entries:
            if isinstance(entry.get('quality', eval_lazy=False), str):
                logger.debug(
                    'Quality is already set to {} for {}, but has not been instantiated properly.',
                    entry['quality'],
                    entry['title'],
                )
                entry['quality'] = qualities.Quality(entry.get('quality', eval_lazy=False))
            else:
                entry.add_lazy_fields(self.get_quality, ['quality'])

    @register_lazy_lookup('quality')
    def get_quality(self, entry):
        if entry.get('quality', eval_lazy=False):
            logger.debug(
                'Quality is already set to {} for {}, skipping quality detection.',
                entry['quality'],
                entry['title'],
            )
            return
        entry['quality'] = qualities.Quality(entry['title'])
        if entry['quality']:
            logger.trace('Found quality {} for {}', entry['quality'], entry['title'])


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoQuality, 'metainfo_quality', api_ver=2, builtin=True)
