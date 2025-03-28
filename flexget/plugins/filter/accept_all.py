from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='accept_all')


class FilterAcceptAll:
    """Just accepts all entries.

    Example::

      accept_all: true
    """

    schema = {'type': 'boolean', 'description': 'Accepts all entries'}

    def on_task_filter(self, task, config):
        if config:
            for entry in task.entries:
                entry.accept()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterAcceptAll, 'accept_all', api_ver=2)
