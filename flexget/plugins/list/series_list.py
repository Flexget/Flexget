from __future__ import unicode_literals, division, absolute_import

import logging
from collections import MutableSet
from datetime import datetime

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from sqlalchemy import Column, Unicode, Integer, ForeignKey, Boolean, DateTime, String, func
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_

from flexget.plugins.filter.series import FilterSeriesBase
from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.utils.database import json_synonym, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.tools import split_title_year

log = logging.getLogger('series_list')
Base = versioned_base('series_list', 0)

SUPPORTED_IDS = FilterSeriesBase().supported_ids
SETTINGS_SCHEMA = FilterSeriesBase().settings_schema
SERIES_ATTRIBUTES = SETTINGS_SCHEMA['properties']


class SeriesListList(Base):
    __tablename__ = 'series_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    series = relationship('SeriesListSeries', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<SeriesListList name=%d>' % (self.id)

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

    # Internal series attributes
    set = Column(Unicode)
    path = Column(Unicode)
    _alternate_name = Column('alternate_name', Unicode)
    alternate_name = json_synonym('_alternate_name')
    _name_regexp = Column('name_regexp', Unicode)
    name_regexp = json_synonym('_name_regexp')
    _ep_regexp = Column('ep_regexp', Unicode)
    ep_regexp = json_synonym('_ep_regexp')
    _date_regexp = Column('date_regexp', Unicode)
    date_regexp = json_synonym('_date_regexp')
    _sequence_regexp = Column('sequence_regexp', Unicode)
    sequence_regexp = json_synonym('_sequence_regexp')
    _id_regexp = Column('id_regexp', Unicode)
    id_regexp = json_synonym('_id_regexp')
    date_yearfirst = Column(Boolean)
    date_dayfirst = Column(Boolean)
    quality = Column(Unicode)  # Todo: enforce format
    _qualities = Column('qualities', Unicode)
    qualities = json_synonym('_qualities')  # Todo: enforce format
    timeframe = Column(Unicode)  # Todo: enforce format
    upgrade = Column(Boolean)
    target = Column(Unicode)  # Todo: enforce format
    specials = Column(Boolean)
    propers = Column(Unicode)  # Todo: enforce format
    identified_by = Column(String)
    exact = Column(Boolean)
    begin = Column(Unicode)  # Todo: enforce format
    _from_group = Column('from_group', Unicode)
    from_group = json_synonym('_from_group')
    parse_only = Column(Boolean)
    _special_ids = Column('special_ids', Unicode)
    special_ids = json_synonym('_special_ids')
    prefer_specials = Column(Boolean)
    assume_special = Column(Boolean)
    tracking = Column(Unicode)  # Todo: enforce format

    list_id = Column(Integer, ForeignKey(SeriesListList.id), nullable=False)
    ids = relationship('SeriesListID', backref='series', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<SeriesListSeries title=%s,list_id=%d>' % (self.title, self.list_id)

    def to_entry(self, strip_year=False):
        entry = Entry()
        entry['title'] = entry['series_name'] = self.title
        entry['url'] = 'mock://localhost/series_list/%d' % self.id
        for attribute in SERIES_ATTRIBUTES:
            if getattr(self, attribute):
                # Maintain support for configure_series plugin expected format
                entry['configure_series_' + attribute] = entry[attribute] = getattr(self, attribute)
        for series_list_id in self.ids:
            entry[series_list_id.id_name] = series_list_id.id_value
        return entry

    def to_dict(self):
        series_list_ids = [series_list_id.to_dict() for series_list_id in self.ids]
        series_dict = {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'list_id': self.list_id,
            'series_list_ids': series_list_ids
        }
        for attribute in SETTINGS_SCHEMA['properties']:
            series_dict[attribute] = getattr(self, attribute) if getattr(self, attribute) else None
        return series_dict


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
            'series_id': self.movie_id
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
        db_list = self._db_list(session)
        if not db_list:
            session.add(SeriesListList(name=self.list_name))

    @with_session
    def __iter__(self, session=None):
        return iter([series.to_entry() for series in self._db_list(session).series])

    @with_session
    def __len__(self, session=None):
        return len(self._db_list(session).series)

    @with_session
    def add(self, entry, session=None):
        # Check if this is already in the list, refresh info if so
        db_list = self._db_list(session=session)
        db_series = self._find_entry(entry, session=session)
        # Just delete and re-create to refresh
        if db_series:
            session.delete(db_series)
        db_series = SeriesListSeries()
        # Setting series title
        if 'series_name' in entry:
            db_series.title = entry['series_name']
        else:
            db_series.title = entry['title']
        # Setting series attributes
        for attribute in SERIES_ATTRIBUTES:
            if entry.get(attribute):
                setattr(db_series, attribute, entry['attribute'])
        # Get list of supported identifiers
        for id_name in SUPPORTED_IDS:
            if entry.get(id_name):
                db_series.ids.append(SeriesListID(id_name=id_name, id_value=entry[id_name]))
        log.debug('adding entry %s', entry)
        db_list.series.append(db_series)
        session.commit()
        return db_series.to_entry()

    @with_session
    def discard(self, entry, session=None):
        db_series = self._find_entry(entry, session=session)
        if db_series:
            log.debug('deleting series %s', db_series)
            session.delete(db_series)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    @with_session
    def _find_entry(self, entry, session=None):
        """Finds `SeriesListSeries` corresponding to this entry, if it exists."""
        for id_name in SUPPORTED_IDS:
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
        # Fall back to title
        name = entry.get('series_name')
        if not name:
            log.verbose('no series name to match, skipping')
            return
        log.debug('trying to match series based of name: %s ', name)
        res = (self._db_list(session).series.filter(SeriesListSeries.title == name.lower()).first())
        if res:
            log.debug('found series %s', res)
        return res

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    @with_session
    def get(self, entry, session):
        match = self._find_entry(entry=entry, session=session)
        return match.to_entry() if match else None


class PluginSeriesList(object):
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return SeriesList(config)

    def on_task_input(self, task, config):
        return list(SeriesList(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSeriesList, 'series_list', api_ver=2, groups=['list'])
