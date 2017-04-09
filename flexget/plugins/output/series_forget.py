from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

try:
    from flexget.plugins.filter.series import remove_series_entity
except ImportError:
    raise plugin.DependencyError(issued_by='series_remove', missing='series',
                                 message='series_forget plugin need series plugin to work')

log = logging.getLogger('series_forget')


class OutputSeriesRemove(object):
    schema = {'type': 'boolean'}

    def on_task_output(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            if 'series_name' in entry and 'series_id' in entry:
                try:
                    remove_series_entity(entry['series_name'], entry['series_id'])
                    log.info('Removed episode `%s` from series `%s` download history.' %
                             (entry['series_id'], entry['series_name']))
                except ValueError:
                    log.debug('Series (%s) or id (%s) unknown.' % (entry['series_name'], entry['series_id']))


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSeriesRemove, 'series_remove', api_ver=2)
