from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.task import TaskAbort

log = logging.getLogger('inputs')


class PluginInputs(object):
    """
    Allows the same input plugin to be configured multiple times in a task.

    Example::

      inputs:
        - rss: http://feeda.com
        - rss: http://feedb.com
    """

    schema = {
        'type': 'array',
        'items': {'allOf': [{'$ref': '/schema/plugins'}, {'minProperties': 1}]}
    }

    def on_task_input(self, task, config):
        entries = []
        entry_titles = set()
        entry_urls = set()
        for index, item in enumerate(config):
            # This turns off auto_accept so that entries can be transferred directly to main task
            # Perhaps it should keep it on, then reset and inject only accepted entries
            subtask = task.make_subtask('/inputs/%s' % index, item, options={'auto_accept': False})
            try:
                subtask.execute()
            except TaskAbort as e:
                log.warning('Error during input number %s: %s' % (index, e))
                continue

            result = subtask.all_entries
            if not result:
                msg = 'Input %s did not return anything' % index
                if getattr(subtask, 'no_entries_ok', False):
                    log.verbose(msg)
                else:
                    log.warning(msg)
                continue
            for entry in result:
                if entry['title'] in entry_titles:
                    log.debug('Title `%s` already in entry list, skipping.' % entry['title'])
                    continue
                urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                if any(url in entry_urls for url in urls):
                    log.debug('URL for `%s` already in entry list, skipping.' % entry['title'])
                    continue
                entries.append(entry)
                entry_titles.add(entry['title'])
                entry_urls.update(urls)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInputs, 'inputs', api_ver=2)
