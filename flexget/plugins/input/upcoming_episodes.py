from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.sql import and_

from flexget import options, plugin
from flexget.plugin import get_plugin_by_name
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.api_tvrage import TVRageEpisodes, TVRageSeries, lookup_series, TVRageLookup
from flexget.plugins.filter.series import SeriesTask
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('upcoming_episodes')


class UpcomingEpisodes(object):
    """
    Returns upcoming shows.

    Example::

      upcoming_episodes: now

    Returns upcoming shows from now.
    """

    schema = {
        'oneOf': [
            {'type': 'string', 'format': 'interval'},
            {'type': 'string', 'enum': ['epoch', 'now', 'season']}
        ]
    }

    def get_from(self, config):
        """Return datetime from given interval in config."""
        if config == 'epoch':
            return datetime.min
        elif config == 'now':
            return datetime.now()
        else:
            try:
                return datetime.now() + parse_timedelta(config)
            except ValueError:
                raise plugin.PluginError('Invalid interval format', log)

    def on_task_input(self, task, config):
        task_series = task.session.query(SeriesTask).\
                      filter(SeriesTask.name == task.name).all()

        # Update episode information based on the name
        names = set([t.series.name.lower() for t in task_series])
        for n in names:
            try:
                lookup_series(name=n)
            except LookupError:
                log.warning('TV shows %s not found, skipping', n)

        # Get tvrage ids of corresponding shows
        ids = task.session.query(TVRageLookup.series_id).filter(TVRageLookup.name.in_(names)).all()
        ids = [id for (id, ) in ids if id]

        if config == 'season':
            sq = task.session.query(TVRageEpisodes.tvrage_series_id,
                                    func.max(TVRageEpisodes.season).label('season')).\
                group_by(TVRageEpisodes.tvrage_series_id).subquery()

            upcoming_eps = task.session.query(TVRageEpisodes).join(TVRageSeries).\
                           join(sq, and_(TVRageSeries.id == sq.c.tvrage_series_id,
                                         sq.c.season == TVRageEpisodes.season)).\
                           filter(TVRageEpisodes.airdate != None).\
                           filter(TVRageSeries.id.in_(ids)).all()

        else:
            from_date = self.get_from(config)
            upcoming_eps = task.session.query(TVRageEpisodes).\
                           join(TVRageSeries).\
                           filter(TVRageEpisodes.airdate > from_date).\
                           filter(TVRageSeries.id.in_(ids)).all()

        entries = []
        for e in upcoming_eps:
            entry = Entry(title=e.title,
                          series_name=e.series.name,
                          series_season=e.season,
                          series_episode=e.episode,
                          url='',
                          series_id_type='ep',
                          series_id='S%02dE%02d' % (e.season, e.episode),
                          tvrage_airdate=e.airdate)
            entry.accept()
            entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UpcomingEpisodes, 'upcoming_episodes', api_ver=2)
