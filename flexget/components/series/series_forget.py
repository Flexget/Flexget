from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event

from . import db

log = logging.getLogger('series_forget')


class OutputSeriesRemove(object):
    schema = {'type': 'boolean'}

    def on_task_output(self, task, config):
        if not config:
            return
        for entry in task.accepted:
            if 'series_name' in entry and 'series_id' in entry:
                try:
                    db.remove_series_entity(entry['series_name'], entry['series_id'])
                    log.info(
                        'Removed episode `%s` from series `%s` download history.'
                        % (entry['series_id'], entry['series_name'])
                    )
                except ValueError:
                    log.debug(
                        'Series (%s) or id (%s) unknown.'
                        % (entry['series_name'], entry['series_id'])
                    )


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSeriesRemove, 'series_remove', api_ver=2)
