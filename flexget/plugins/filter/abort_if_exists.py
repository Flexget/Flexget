import re

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='abort_if_exists')


class PluginAbortIfExists:
    """Aborts a task if an entry field matches the regexp"""

    schema = {
        'type': 'object',
        'properties': {
            'regexp': {'type': 'string', 'format': 'regex'},
            'field': {'type': 'string'},
        },
        'required': ['regexp', 'field'],
        'additionalProperties': False,
    }

    # Execute as the first thing in filter phase
    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        abort_re = re.compile(config['regexp'], re.IGNORECASE)
        field = config['field']
        for entry in task.all_entries:
            # if pattern matches any entry
            if field not in entry:
                logger.debug('Field {} not found. Skipping.', field)
                continue
            if abort_re.search(entry[field]):
                task.abort('An entry contained %s in field %s. Abort!' % (config['regexp'], field))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginAbortIfExists, 'abort_if_exists', api_ver=2)
