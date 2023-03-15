from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils import qualities

logger = logger.bind(name='quality')


class FilterQuality:
    """
    Rejects all entries that don't have one of the specified qualities

    Example::

      quality:
        - hdtv
    """

    schema = one_or_more({'type': 'string', 'format': 'quality_requirements'})

    # Run before series and imdb plugins, so correct qualities are chosen
    @plugin.priority(175)
    def on_task_filter(self, task, config):
        if not isinstance(config, list):
            config = [config]
        reqs = [qualities.Requirements(req) for req in config]
        for entry in task.entries:
            if entry.get('quality') is None:
                entry.reject('Entry doesn\'t have a quality')
                continue
            if not any(req.allows(entry['quality']) for req in reqs):
                text_reqs = ', '.join(f'`{req}`' for req in reqs)
                entry.reject(
                    f'`{entry["quality"]}` does not match any of quality requirements: {text_reqs}'
                )


@event('plugin.register')
def register_plugin():
    plugin.register(FilterQuality, 'quality', api_ver=2)
