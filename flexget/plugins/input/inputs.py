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
            subtask = task.make_subtask('/inputs/%s' % index, item)
            try:
                subtask.execute()
            except TaskAbort as e:
                log.warning('Error during input number %s: %s' % (index, e))
                continue

            if not subtask.all_entries:
                msg = 'Input %s did not return anything' % index
                if getattr(subtask, 'no_entries_ok', False):
                    log.verbose(msg)
                else:
                    log.warning(msg)
                continue
            for entry in subtask.all_entries:
                if not entry.accepted:
                    continue
                if entry['title'] in entry_titles:
                    log.debug('Title `%s` already in entry list, skipping.' % entry['title'])
                    continue
                urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                if any(url in entry_urls for url in urls):
                    log.debug('URL for `%s` already in entry list, skipping.' % entry['title'])
                    continue
                entry.reset('resetting before injection into parent task')
                entries.append(entry)
                entry_titles.add(entry['title'])
                entry_urls.update(urls)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInputs, 'inputs', api_ver=2)
