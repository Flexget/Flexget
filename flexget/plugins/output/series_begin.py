from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.plugins.filter import series as plugin_series
except ImportError:
    raise plugin.DependencyError(
        issued_by=__name__, missing='series',
    )

log = logging.getLogger('set_series_begin')


class SetSeriesBegin(object):
    """
    Set the first episode for series. Uses series_name and series_id.

    Example::

      set_series_begin: yes

    """

    schema = {'type': 'boolean'}

    def on_task_output(self, task, config):
        if not (config and task.accepted):
            return
        for entry in task.accepted:
            if entry.get('series_name') and entry.get('series_id'):
                fshow = task.session.query(plugin_series.Series).filter(
                    plugin_series.Series.name == entry['series_name']).first()
                if not fshow:
                    fshow = plugin_series.Series()
                    fshow.name = entry['series_name']
                    task.session.add(fshow)
                try:
                    plugin_series.set_series_begin(fshow, entry['series_id'])
                except ValueError as e:
                    log.error('An error occurred trying to set begin for %s: %s', entry['series_name'], e)
                log.info('First episode for "%s" set to %s', entry['series_name'], entry['series_id'])


@event('plugin.register')
def register_plugin():
    plugin.register(SetSeriesBegin, 'set_series_begin', api_ver=2)
