from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='require_field')


class FilterRequireField:
    """
    Rejects entries without defined field.

    Example::

      require_field: imdb_url
    """

    schema = one_or_more({'type': 'string'})

    @plugin.priority(32)
    def on_task_filter(self, task, config):
        if isinstance(config, str):
            config = [config]
        for entry in task.entries:
            for field in config:
                if field not in entry:
                    entry.reject('Required field %s is not present' % field)
                    break
                if entry[field] is None:
                    entry.reject('Required field %s is `None`' % field)
                    break


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRequireField, 'require_field', api_ver=2)
