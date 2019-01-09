from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.entry import is_show, is_movie

log = logging.getLogger('metainfo_media_id')


class MetainfoMediaId(object):
    """
    Populate media_id field based on media type etc.
    """

    schema = {'type': 'boolean'}

    @plugin.priority(0)  # run after other metainfo plugins in case they set the id field
    def on_task_metainfo(self, task, config):
        # Don't run if we are disabled
        if config is False:
            return
        for entry in task.entries:
            entry.register_lazy_func(self.get_media_id, ['media_id'])

    @staticmethod
    def get_media_id(entry):
        if entry.get('id'):
            entry['media_id'] = entry['id']
            return

        # I guess we need to generate one then. Robustness of this section is highly debatable
        entry_id = None
        if is_movie(entry):
            entry_id = entry['movie_name']
            if entry.get('movie_year'):
                entry_id += ' ' + entry['movie_year']
        elif is_show(entry):
            entry_id = entry['series_name']
            if entry.get('series_year'):
                entry_id += ' ' + entry['series_year']
            series_id = None
            if entry.get('series_episode'):
                if entry.get('series_season'):
                    series_id = (entry.get('series_season'), entry.get('series_episode'))
                else:
                    series_id = (0, entry.get('series_episode'))
            elif entry.get('series_season'):
                series_id = (entry['series_season'], 0)
            elif entry.get('series_date'):
                series_id = entry['series_date']
            if series_id:
                entry_id += ' ' + series_id

        if entry_id:
            entry_id = entry_id.strip().lower()

        entry['media_id'] = entry_id


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoMediaId, 'metainfo_media_id', api_ver=2, builtin=True)
