from __future__ import unicode_literals, division, absolute_import

import logging
from collections import MutableSet
from datetime import datetime

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from sqlalchemy import Column, Unicode, Integer, ForeignKey, Boolean, DateTime, String, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.sql.elements import and_

from flexget.plugins.filter.series import FilterSeriesBase
from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.utils.database import with_session
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('series_list')
Base = versioned_base('series_list', 0)

SETTINGS_SCHEMA = FilterSeriesBase().settings_schema
SERIES_ATTRIBUTES = SETTINGS_SCHEMA['properties']


def supported_ids():
    # Return a list of supported series identifier as registered via their plugins
    ids = []
    for p in plugin.get_plugins(group='series_metainfo'):
        ids.append(p.instance.series_identifier())
    return ids


class SeriesListList(Base):
    __tablename__ = 'series_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    series = relationship('SeriesListSeries', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<SeriesListList name=%d>' % self.id

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
    path = Column(Unicode)
    alternate_name = relationship('SeriesListAlternateName', backref='series', cascade='all, delete, delete-orphan')
    name_regexp = relationship('SeriesListNameRegexp', backref='series', cascade='all, delete, delete-orphan')
    ep_regexp = relationship('SeriesListEpRegexp', backref='series', cascade='all, delete, delete-orphan')
    date_regexp = relationship('SeriesListDateRegexp', backref='series', cascade='all, delete, delete-orphan')
    sequence_regexp = relationship('SeriesListSequenceRegexp', backref='series', cascade='all, delete, delete-orphan')
    id_regexp = relationship('SeriesListIDRegexp', backref='series', cascade='all, delete, delete-orphan')
    date_yearfirst = Column(Boolean)
    date_dayfirst = Column(Boolean)
    quality = relationship('SeriesListQuality', uselist=False, backref='series', cascade='all, delete, delete-orphan')
    qualities = relationship('SeriesListQualities', backref='series',
                             cascade='all, delete, delete-orphan')
    timeframe = Column(Unicode)
    upgrade = Column(Boolean)
    target = Column(Unicode)
    specials = Column(Boolean)
    propers = Column(Unicode)
    identified_by = Column(String)
    exact = Column(Boolean)
    begin = Column(Unicode)
    from_group = relationship('SeriesListFromGroup', backref='series', cascade='all, delete, delete-orphan')
    parse_only = Column(Boolean)
    special_ids = relationship('SeriesListSpecialID', backref='series', cascade='all, delete, delete-orphan')
    prefer_specials = Column(Boolean)
    assume_special = Column(Boolean)
    tracking = Column(Unicode)

    list_id = Column(Integer, ForeignKey(SeriesListList.id), nullable=False)
    ids = relationship('SeriesListSeriesExternalID', backref='series', cascade='all, delete, delete-orphan')

    def __init__(self, title):
        self.title = title

    def __repr__(self):
        return '<SeriesListSeries title=%s,list_id=%d>' % (self.title, self.list_id)

    def format_converter(self, attribute):
        """
        Return correct attribute format, based on schema. This is needed to maintain consistency with multi
        type schema formats, and convert instrumented lists on the fly
        """
        value = getattr(self, attribute)
        if not value:
            return
        if isinstance(value, InstrumentedList):
            if attribute.endswith('regexp'):
                return [regexp.regexp for regexp in value]
            elif attribute == 'alternate_name':
                return [alternate_name.name for alternate_name in value]
            elif attribute == 'qualities':
                return [quality.quality for quality in value]
            elif attribute == 'from_group':
                return [group.group_name for group in value]
            elif attribute == 'special_ids':
                return [special_id.id_name for special_id in value]
        if attribute in ['propers', 'tracking']:
            # Value can be either bool or unicode
            if value in ['0', '1']:
                return bool(value)
        if attribute == 'quality':
            return value.quality
        return value

    def to_entry(self):
        entry = Entry()
        entry['title'] = entry['series_name'] = self.title
        entry['url'] = 'mock://localhost/series_list/%d' % self.id
        entry['set'] = {}

        for attribute in SERIES_ATTRIBUTES:
            # `set` is not a real series attribute and is just a way to pass IDs in task.
            if attribute == 'set':
                continue
            result = self.format_converter(attribute)
            if result:
                # Maintain support for configure_series plugin expected format
                entry['configure_series_' + attribute] = entry[attribute] = result
        for series_list_id in self.ids:
            entry[series_list_id.id_name] = series_list_id.id_value
            entry['set'].update({series_list_id.id_name: series_list_id.id_value})
        return entry

    def to_dict(self):
        series_dict = {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'list_id': self.list_id,
            'series_list_identifiers': [series_list_id.to_dict() for series_list_id in self.ids]
        }
        for attribute in SETTINGS_SCHEMA['properties']:
            # `set` is not a real series attribute and is just a way to pass IDs in task.
            if attribute == 'set':
                continue
            series_dict[attribute] = self.format_converter(attribute)
        return series_dict


class SeriesListSeriesExternalID(Base):
    __tablename__ = 'series_list_series_external_ids'
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


class SeriesListAlternateName(Base):
    __tablename__ = 'series_list_alternate_names'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListNameRegexp(Base):
    __tablename__ = 'series_list_name_regexps'

    id = Column(Integer, primary_key=True)
    regexp = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListEpRegexp(Base):
    __tablename__ = 'series_list_ep_regexps'

    id = Column(Integer, primary_key=True)
    regexp = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListDateRegexp(Base):
    __tablename__ = 'series_list_date_regexps'

    id = Column(Integer, primary_key=True)
    regexp = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListSequenceRegexp(Base):
    __tablename__ = 'series_list_sequence_regexps'

    id = Column(Integer, primary_key=True)
    regexp = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListIDRegexp(Base):
    __tablename__ = 'series_list_id_regexps'

    id = Column(Integer, primary_key=True)
    regexp = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListQuality(Base):
    __tablename__ = 'series_list_quality'

    id = Column(Integer, primary_key=True)
    quality = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListQualities(Base):
    __tablename__ = 'series_list_qualities'

    id = Column(Integer, primary_key=True)
    quality = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListFromGroup(Base):
    __tablename__ = 'series_list_from_groups'

    id = Column(Integer, primary_key=True)
    group_name = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


class SeriesListSpecialID(Base):
    __tablename__ = 'series_list_special_ids'

    id = Column(Integer, primary_key=True)
    id_name = Column(Unicode)
    added = Column(DateTime, default=datetime.now)
    series_id = Column(Integer, ForeignKey(SeriesListSeries.id))


def get_db_series(entry):
    title = entry.get('series_name') or entry['title']
    db_series = SeriesListSeries(title)
    # Setting series attributes only for received data
    single_attributes = ['date_dayfirst', 'date_yearfirst', 'timeframe', 'upgrade', 'target', 'specials', 'propers',
                         'identified_by', 'exact', 'begin', 'parse_only', 'prefer_specials', 'assume_special',
                         'tracking']
    for attribute in single_attributes:
        if entry.get(attribute):
            setattr(db_series, attribute, entry.get(attribute))
    if entry.get('alternate_name'):
        db_series.alternate_name = [SeriesListAlternateName(name=name) for name in entry.get('alternate_name')]
    if entry.get('name_regexp'):
        db_series.name_regexp = [SeriesListNameRegexp(regexp=regexp) for regexp in entry.get('name_regexp')]
    if entry.get('ep_regexp'):
        db_series.ep_regexp = [SeriesListEpRegexp(regexp=regexp) for regexp in entry.get('ep_regexp')]
    if entry.get('date_regexp'):
        db_series.date_regexp = [SeriesListDateRegexp(regexp=regexp) for regexp in entry.get('date_regexp')]
    if entry.get('sequence_regexp'):
        db_series.sequence_regexp = [SeriesListSequenceRegexp(regexp=regexp) for regexp in entry.get('sequence_regexp')]
    if entry.get('id_regexp'):
        db_series.id_regexp = [SeriesListIDRegexp(regexp=regexp) for regexp in entry.get('id_regexp')]
    if entry.get('quality'):
        db_series.quality = SeriesListQuality(quality=entry.get('quality'))
    if entry.get('qualities'):
        db_series.qualities = [SeriesListQualities(quality=quality) for quality in entry.get('qualities')]
    if entry.get('from_group'):
        db_series.from_group = [SeriesListFromGroup(group_name=name) for name in entry.get('from_group')]
    if entry.get('special_ids'):
        db_series.special_ids = [SeriesListSpecialID(id_name=name) for name in entry.get('special_ids')]

    # Get list of supported identifiers
    for id_name in supported_ids():
        value = entry.get(id_name)
        if value:
            log.debug('found supported ID %s with value %s in entry, adding to series', id_name, value)
            db_series.ids.append(SeriesListSeriesExternalID(id_name=id_name, id_value=value))
    return db_series


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
        db_series = get_db_series(entry)
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
        for id_name in supported_ids():
            if entry.get(id_name):
                log.debug('trying to match series based off id %s: %s', id_name, entry[id_name])
                res = (self._db_list(session).series.join(SeriesListSeries.ids).filter(
                    and_(
                        SeriesListSeriesExternalID.id_name == id_name,
                        SeriesListSeriesExternalID.id_value == entry[id_name]))
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


class SeriesListDBContainer(object):
    """ A container class to hold DB methods for this plugin"""

    @staticmethod
    @with_session
    def get_series_lists(name=None, session=None):
        log.debug('retrieving series lists')
        query = session.query(SeriesListList)
        if name:
            log.debug('filtering by name %s', name)
            query = query.filter(SeriesListList.name == name)
        return query.all()

    @staticmethod
    @with_session
    def get_list_by_id(list_id, session=None):
        log.debug('fetching list with id %d', list_id)
        return session.query(SeriesListList).filter(SeriesListList.id == list_id).one()

    @staticmethod
    @with_session
    def get_series_by_list_id(list_id, count=False, start=None, stop=None, order_by='added', descending=False,
                              session=None):
        query = session.query(SeriesListSeries).filter(SeriesListSeries.list_id == list_id)
        if count:
            return query.count()
        if descending:
            query = query.order_by(getattr(SeriesListSeries, order_by).desc())
        else:
            query = query.order_by(getattr(SeriesListSeries, order_by))
        query = query.slice(start, stop)
        return query.all()

    @staticmethod
    @with_session
    def get_list_by_exact_name(name, session=None):
        log.debug('returning list with name %s', name)
        return session.query(SeriesListList).filter(func.lower(SeriesListList.name) == name.lower()).one()

    @staticmethod
    @with_session
    def get_series_by_title(list_id, title, session=None):
        series_list = SeriesListDBContainer.get_list_by_id(list_id=list_id, session=session)
        if series_list:
            log.debug('searching for series %s in list %d', title, list_id)
            return session.query(SeriesListSeries).filter(
                and_(
                    func.lower(SeriesListSeries.title) == title.lower(),
                    SeriesListSeries.list_id == list_id)
            ).first()

    @staticmethod
    @with_session
    def get_series_by_id(list_id, series_id, session=None):
        log.debug('fetching series with id %d from list id %d', series_id, list_id)
        return session.query(SeriesListSeries).filter(
            and_(SeriesListSeries.id == series_id, SeriesListSeries.list_id == list_id)).one()


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSeriesList, 'series_list', api_ver=2, groups=['list'])
