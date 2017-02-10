from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from collections import MutableSet
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer, ForeignKey, func, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt
from flexget.utils.tools import split_title_year

log = logging.getLogger('series_list')
Base = versioned_base('series_list', 0)


class SeriesListBase(object):
    """
    Class that contains helper methods for series list as well as plugins that use it,
    such as API and CLI.
    """

    @property
    def supported_ids(self):
        # Return a list of supported series identifier as registered via their plugins
        return [p.instance.series_identifier for p in plugin.get_plugins(interface='series_metainfo')]


class SeriesListList(Base):
    __tablename__ = 'series_list_lists'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    series = relationship('SeriesListSeries', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<SeriesListList,name={}id={}>'.format(self.name, self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'added_on': self.added
        }


class SeriesListSeries(Base):
    __tablename__ = 'series_list_series'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    year = Column(Integer)
    list_id = Column(Integer, ForeignKey(SeriesListList.id), nullable=False)
    ids = relationship('SeriesListID', backref='series', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<SeriesListSeries title=%s,year=%s,list_id=%d>' % (self.title, self.year, self.list_id)

    def to_entry(self, strip_year=False):
        entry = Entry()
        entry['title'] = entry['series_name'] = self.title
        entry['url'] = 'mock://localhost/series_list/%d' % self.id
        entry['added'] = self.added
        if self.year:
            if strip_year is False:
                entry['title'] += ' (%d)' % self.year
            entry['series_year'] = self.year
        for series_list_id in self.ids:
            entry[series_list_id.id_name] = series_list_id.id_value
        return entry

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'year': self.year,
            'list_id': self.list_id,
            'series_list_ids': [series_list_id.to_dict() for series_list_id in self.ids]
        }

    @property
    def identifiers(self):
        """ Return a dict of series identifiers """
        return {identifier.id_name: identifier.id_value for identifier in self.ids}


class SeriesListID(Base):
    __tablename__ = 'series_list_ids'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    id_name = Column(Unicode)
    id_value = Column(Unicode)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))

    def __repr__(self):
        return '<SeriesListID id_name=%s,id_value=%s,series_id=%d>' % (self.id_name, self.id_value, self.series_id)

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'id_name': self.id_name,
            'id_value': self.id_value,
            'series_id': self.series_id
        }


class SeriesList(MutableSet):
    def _db_list(self, session):
        return session.query(SeriesListList).filter(SeriesListList.name == self.list_name).first()

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @with_session
    def __init__(self, config, session=None):
        if not isinstance(config, dict):
            config = {'list_name': config}
        config.setdefault('strip_year', False)
        self.list_name = config.get('list_name')
        self.strip_year = config.get('strip_year')

        db_list = self._db_list(session)
        if not db_list:
            session.add(SeriesListList(name=self.list_name))

    def __iter__(self):
        with Session() as session:
            return iter([series.to_entry(self.strip_year) for series in self._db_list(session).series])

    def __len__(self):
        with Session() as session:
            return len(self._db_list(session).series)

    def add(self, entry):
        with Session() as session:
            # Check if this is already in the list, refresh info if so
            db_list = self._db_list(session=session)
            db_series = self._find_entry(entry, session=session)
            # Just delete and re-create to refresh
            if db_series:
                session.delete(db_series)
            db_series = SeriesListSeries()
            if 'series_name' in entry:
                db_series.title, db_series.year = entry['series_name'], entry.get('series_year')
            else:
                db_series.title, db_series.year = split_title_year(entry['title'])
            for id_name in SeriesListBase().supported_ids:
                if id_name in entry:
                    db_series.ids.append(SeriesListID(id_name=id_name, id_value=entry[id_name]))
            log.debug('adding entry %s', entry)
            db_list.series.append(db_series)
            session.commit()
            return db_series.to_entry()

    def discard(self, entry):
        with Session() as session:
            db_series = self._find_entry(entry, session=session)
            if db_series:
                log.debug('deleting series %s', db_series)
                session.delete(db_series)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    @with_session
    def _find_entry(self, entry, session=None):
        """Finds `SeriesListSeries` corresponding to this entry, if it exists."""
        # Match by supported IDs
        for id_name in SeriesListBase().supported_ids:
            if entry.get(id_name):
                log.debug('trying to match series based off id %s: %s', id_name, entry[id_name])
                res = (self._db_list(session).series.join(SeriesListSeries.ids).filter(
                    and_(
                        SeriesListID.id_name == id_name,
                        SeriesListID.id_value == entry[id_name]))
                       .first())
                if res:
                    log.debug('found series %s', res)
                    return res
        # Fall back to title/year match
        if entry.get('series_name'):
            name = entry['series_name']
            year = entry.get('series_year') if entry.get('series_year') else None
        else:
            log.warning('Could not get a series name, skipping')
            return
        log.debug('trying to match series based of name: %s and year: %s', name, year)
        res = (self._db_list(session).series.filter(func.lower(SeriesListSeries.title) == name.lower())
               .filter(SeriesListSeries.year == year).first())
        if res:
            log.debug('found series %s', res)
        return res

    @staticmethod
    def _parse_title(entry):
        parser = get_plugin_by_name('parsing').instance.parse_series(data=entry['title'])
        if parser and parser.valid:
            parser.name = normalize_name(remove_dirt(parser.name))
            entry.update(parser.fields)

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """
        Set the online status of the plugin, online plugin should be treated
        differently in certain situations, like test mode
        """
        return False

    @with_session
    def get(self, entry, session):
        match = self._find_entry(entry=entry, session=session)
        return match.to_entry() if match else None


class PluginSeriesList(object):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    schema = {'oneOf': [
        {'type': 'string'},
        {'type': 'object',
         'properties': {
             'list_name': {'type': 'string'},
             'strip_year': {'type': 'boolean'}
         },
         'required': ['list_name'],
         'additionalProperties': False
         }
    ]}

    @staticmethod
    def get_list(config):
        return SeriesList(config)

    def on_task_input(self, task, config):
        return list(SeriesList(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSeriesList, 'series_list', api_ver=2, interfaces=['task', 'list'])
