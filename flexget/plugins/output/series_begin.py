from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import Series, set_series_begin

log = logging.getLogger('series_begin')


class SetSeriesBegin(object):
    """
    Set the first episode for series.
    
    Example (using trakt_list with series/watched)::

      series_begin:
        series_field: 'title'
        episode_field: 'last_seen_ep_id'
    
    """

    schema = {
        'type': 'object',
        'properties': {
            'series_field': {'type': 'string'},
            'episode_field': {'type': 'string'},
            'add_series': {'type': 'boolean', 'default': True}
        },
        'required': ['series_field', 'episode_field'],
        'additionalProperties': False
    }
    
    def on_task_output(self, task, config):
        if not task.accepted:
            return
        for entry in task.accepted:
            title = entry.get(config['series_field'], None)
            lepid = entry.get(config['episode_field'], None)
            if title and lepid:
                fshow = task.session.query(Series).filter(Series.name == title).first()
                if not fshow:
                    if not config['add_series']:
                        continue
                    fshow = Series()
                    fshow.name = title
                    task.session.add(fshow)
                try:
                    set_series_begin(fshow, lepid)
                except ValueError as e:
                    self.log.error('An error occurred trying to set the series first episode: ' % e)
                self.log.info('First episode for "%s" set to %s' % (title, lepid))

@event('plugin.register')
def register_plugin():
    plugin.register(SetSeriesBegin, 'series_begin', api_ver=2)
