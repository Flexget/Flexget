from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

from flexget import plugin
from flexget.event import event
import re

log = logging.getLogger('sort_by')

RE_ARTICLES = '^(the|a|an)\s'

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
                    'reverse': {'type': 'boolean'},
                    'ignore_articles': {
                        'oneOf': [
                            {'type': 'boolean'},
                            {'type': 'string', 'format': 'regex'}
                        ]
                    }
                },
                'additionalProperties': False
            }
        ]
    }

    def on_task_filter(self, task, config):
        if isinstance(config, str):
            field = config
            reverse = False
            ignore_articles = False
        else:
            field = config.get('field', None)
            reverse = config.get('reverse', False)
            ignore_articles = config.get('ignore_articles', False)

        log.debug('sorting entries by: %s' % config)

        if not field:
            task.all_entries.reverse()
            return
        
        re_articles = ignore_articles if not isinstance(ignore_articles, bool) else RE_ARTICLES

        if ignore_articles:
            task.all_entries.sort(key=lambda e: re.sub(re_articles, '', e.get(field, 0), flags=re.IGNORECASE),
                                  reverse=reverse)
        else:
            task.all_entries.sort(key=lambda e: e.get(field, 0), reverse=reverse)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSortBy, 'sort_by', api_ver=2)
