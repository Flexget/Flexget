from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re
from datetime import datetime, timedelta
from requests import RequestException

from sqlalchemy import Column, Integer, Unicode, DateTime
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relationship

from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.database import with_session
from flexget.plugins.api_tvdb import lookup_series, TVDBRequest


log = logging.getLogger('thetvdb_favorites')
Base = db_schema.versioned_base('thetvdb_favorites', 0)


@db_schema.upgrade('thetvdb_favorites')
def upgrade(ver, session):
    if ver is None or ver == 0:
        raise db_schema.UpgradeImpossible
    return ver


class TVDBUserFavorite(Base):

    __tablename__ = 'thetvdb_favorites'

    id = Column(Integer, primary_key=True)
    username = Column(Unicode, index=True)
    updated = Column(DateTime)

    _series_ids = relationship('TVDBFavoriteSeries')
    series_ids = association_proxy('_series_ids', 'tvdb_id', creator=lambda _i: TVDBFavoriteSeries(tvdb_id=_i))

    def __repr__(self):
        return '<series_favorites(username=%s, series_id=%s)>' % (self.username, self.series_ids)


class TVDBFavoriteSeries(Base):

    __tablename__ = 'thetvdb_favorite_series'

    id = Column(Integer, primary_key=True)
    user = Column(Unicode, ForeignKey('thetvdb_favorites.id'))
    tvdb_id = Column(Integer)


class InputThetvdbFavorites(object):
    """
    Creates a list of entries for your series marked as favorites at thetvdb.com for use in configure_series.

    Example:

      configure_series:
        from:
          thetvdb_favorites:
            username: some_username
            account_id: some_password
    """
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'account_id': {'type': 'string'},
            'strip_dates': {'type': 'boolean'}
        },
        'required': ['username', 'account_id'],
        'additionalProperties': False
    }

    @cached('thetvdb_favorites')
    @plugin.internet(log)
    @with_session
    def on_task_input(self, task, config, session=None):

        # Get the cache for this user
        user_favorites = session.query(TVDBUserFavorite).filter(TVDBUserFavorite.username == config['username']).first()

        if not user_favorites:
            user_favorites = TVDBUserFavorite(username=config['username'])
            session.add(user_favorites)

        if user_favorites.updated and user_favorites.updated > datetime.now() - timedelta(minutes=10):
            log.debug('Using cached thetvdb favorite series information for account %s' % config['username'])
        else:
            try:
                req = TVDBRequest(username=config['username'], account_id=config['account_id']).get('user/favorites')
                user_favorites.series_ids = [int(f_id) for f_id in req['favorites']]
            except RequestException as e:
                log.error('Error retrieving favorites from thetvdb: %s' % str(e))

            # Successfully updated from tvdb, update the database
            user_favorites.updated = datetime.now()

        # Construct list of entries with our series names
        entries = []
        for series_id in user_favorites.series_ids:
            # Lookup the series name from the id
            try:
                series = lookup_series(tvdb_id=series_id)
            except LookupError as e:
                log.error('Error looking up %s from thetvdb: %s' % (series_id, e.args[0]))
            else:
                series_name = series.name
                if config.get('strip_dates'):
                    # Remove year from end of series name if present
                    series_name = re.sub(r'\s+\(\d{4}\)$', '', series_name)
                entries.append(Entry(series_name, '', tvdb_id=series.id))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputThetvdbFavorites, 'thetvdb_favorites', api_ver=2)
