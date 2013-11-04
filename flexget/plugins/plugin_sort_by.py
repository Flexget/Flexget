from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('sort_by')


class PluginSortBy(object):

    """
    Sort task entries based on a field

    Example::

      sort_by: title

    More complex::

      sort_by:
        field: imdb_score
        reverse: yes

    Reverse the order of the entries, without sorting on a field::

      sort_by:
        reverse: yes
    """

    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {
                    'field': {'type': 'string'},
                    'reverse': {'type': 'boolean'}},
                'additionalProperties': False
            }
        ]
    }

    def on_task_filter(self, task, config):
        if isinstance(config, basestring):
            field = config
            reverse = False
        else:
            field = config.get('field', None)
            reverse = config.get('reverse', False)

        log.debug('sorting entries by: %s' % config)

        if not field:
            task.entries.reverse()
            task.accepted.reverse()
            return

        def cmp_helper(a, b):
            va = a.get(field, 0)
            vb = b.get(field, 0)
            return cmp(va, vb)

        task.entries.sort(cmp_helper, reverse=reverse)
        task.accepted.sort(cmp_helper, reverse=reverse)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSortBy, 'sort_by', api_ver=2)
