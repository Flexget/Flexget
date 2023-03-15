from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once

logger = logger.bind(name='urlfix')


class UrlFix:
    """
    Automatically fix broken urls.
    """

    schema = {'type': 'boolean'}

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_input(self, task, config):
        if config is False:
            return
        for entry in task.entries:
            if '&amp;' in entry['url']:
                log_once(
                    'Corrected `%s` url (replaced &amp; with &)' % entry['title'], logger=logger
                )
                entry['url'] = entry['url'].replace('&amp;', '&')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlFix, 'urlfix', builtin=True, api_ver=2)
