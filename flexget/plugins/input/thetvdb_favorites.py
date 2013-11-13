from __future__ import unicode_literals, division, absolute_import
import logging
import urllib2
import re
from datetime import datetime, timedelta
import xml.etree.ElementTree as ElementTree
from sqlalchemy import Column, Integer, Unicode, DateTime, String
from flexget import db_schema
from flexget.plugin import register_plugin, internet, DependencyError
from flexget.utils.tools import urlopener
from flexget.utils.database import pipe_list_synonym, with_session
from flexget.utils.sqlalchemy_utils import drop_tables, table_columns
from flexget.utils.cached_input import cached
from flexget.entry import Entry

try:
    from flexget.plugins.api_tvdb import lookup_series
except ImportError:
    raise DependencyError(issued_by='thetvdb_favorites', missing='api_tvdb',
                          message='thetvdb_lookup requires the `api_tvdb` plugin')

log = logging.getLogger('thetvdb_favorites')
Base = db_schema.versioned_base('thetvdb_favorites', 0)


@db_schema.upgrade('thetvdb_favorites')
def upgrade(ver, session):
    if ver is None:
        columns = table_columns('thetvdb_favorites', session)
        if not 'series_ids' in columns:
            # Drop the old table
            log.info('Dropping old version of thetvdb_favorites table from db')
            drop_tables(['thetvdb_favorites'], session)
            # Create new table from the current model
            Base.metadata.create_all(bind=session.bind)
        ver = 0
    return ver


class ThetvdbFavorites(Base):

    __tablename__ = 'thetvdb_favorites'

    id = Column(Integer, primary_key=True)
    account_id = Column(String, index=True)
    _series_ids = Column('series_ids', Unicode)
    series_ids = pipe_list_synonym('_series_ids')
    updated = Column(DateTime)

    def __init__(self, account_id, series_ids):
        self.account_id = account_id
        self.series_ids = series_ids
        self.updated = datetime.now()

    def __repr__(self):
        return '<series_favorites(account_id=%s, series_id=%s)>' % (self.account_id, self.series_ids)


class InputThetvdbFavorites(object):
    """
    Creates a list of entries for your series marked as favorites at thetvdb.com for use in import_series.

    Example::

      import_series:
        from:
          thetvdb_favorites:
            account_id: 23098230
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('text', key='account_id', required=True)
        root.accept('boolean', key='strip_dates')
        return root

    @cached('thetvdb_favorites')
    @internet(log)
    @with_session
    def on_task_input(self, task, config, session=None):
        account_id = str(config['account_id'])
        # Get the cache for this user
        user_favorites = session.query(ThetvdbFavorites).filter(ThetvdbFavorites.account_id == account_id).first()
        if user_favorites and user_favorites.updated > datetime.now() - timedelta(minutes=10):
            log.debug('Using cached thetvdb favorite series information for account ID %s' % account_id)
        else:
            try:
                url = 'http://thetvdb.com/api/User_Favorites.php?accountid=%s' % account_id
                log.debug('requesting %s' % url)
                data = ElementTree.fromstring(urlopener(url, log).read())
                favorite_ids = []
                for i in data.findall('Series'):
                    if i.text:
                        favorite_ids.append(i.text)
            except (urllib2.URLError, IOError, AttributeError):
                import traceback
                # If there are errors getting the favorites or parsing the xml, fall back on cache
                log.error('Error retrieving favorites from thetvdb, using cache.')
                log.debug(traceback.format_exc())
            else:
                # Successfully updated from tvdb, update the database
                log.debug('Successfully updated favorites from thetvdb.com')
                if not user_favorites:
                    user_favorites = ThetvdbFavorites(account_id, favorite_ids)
                else:
                    user_favorites.series_ids = favorite_ids
                    user_favorites.updated = datetime.now()
                session.merge(user_favorites)
        if not user_favorites.series_ids:
            log.warning('Didn\'t find any thetvdb.com favorites.')
            return

        # Construct list of entries with our series names
        entries = []
        for series_id in user_favorites.series_ids:
            # Lookup the series name from the id
            try:
                series = lookup_series(tvdb_id=series_id)
            except LookupError as e:
                log.error('Error looking up %s from thetvdb: %s' % (series_id, e.message))
            else:
                series_name = series.seriesname
                if config.get('strip_dates'):
                    # Remove year from end of series name if present
                    series_name = re.sub(r'\s+\(\d{4}\)$', '', series_name)
                entries.append(Entry(series_name, '', tvdb_id=series.id))
        return entries

register_plugin(InputThetvdbFavorites, 'thetvdb_favorites', api_ver=2)
