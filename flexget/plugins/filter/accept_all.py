import logging
from flexget.plugin import register_plugin

log = logging.getLogger('accept_all')


class FilterAcceptAll(object):
    """
        Just accepts all entries.

        Example::

          accept_all: true
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_task_filter(self, task, config):
        if config:
            for entry in task.entries:
                task.accept(entry)

register_plugin(FilterAcceptAll, 'accept_all', api_ver=2)
