from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from collections import MutableSet
from datetime import datetime

from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.plugins.filter.series import Series
from sqlalchemy import Column, Unicode, Integer, DateTime
from sqlalchemy.orm import relationship

log = logging.getLogger('series_list')
Base = versioned_base('series_list', 0)


class SeriesListList(Base):
    __tablename__ = 'series_list_lists'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    series = relationship('Series', backref='series_list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {
            'id': self.id,
            'list_name': self.list_name,
            'added_on': self.added
        }


class SeriesListSet(MutableSet):
    def _db_list(self, session):
        return session.query(SeriesListList).filter(SeriesListList.name == self.config).first()

    def __init__(self, config):
        self.config = config
        with Session() as session:
            if not self._db_list(session):
                session.add(SeriesListList(name=self.config))

    def _from_iterable(self, it):
        return set(it)

    def _find_entry(self, entry):
        with Session() as session:
            log.debug('trying to find series %s in DB', entry['series_name'])
            series = session.query(Series).filter(Series.name == entry['series_name']).one_or_none()
            if series:
                log.debug('found series %s', series.name)
            return series

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def __len__(self):
        with Session() as session:
            return len(self._db_list(session).series)

    def __iter__(self):
        with Session() as session:
            return iter(
                [Entry(title=series.name, url='', series_name=series.name) for series in self._db_list(session).series])

    def add(self, entry):
        with Session() as session:
            if self.__contains__(entry):
                log.debug('series %s already exist in DB, skipping', entry['series_name'])
                return
            db_list = self._db_list(session=session)
            series = Series()
            series.name = entry['series_name']
            log.debug('adding series %s to list %s', series.name, db_list.name)
            db_list.series.append(series)

    def discard(self, entry):
        with Session() as session:
            series = self._find_entry(entry)
            if series:
                log.debug('deleting series %s from DB', series.name)
                session.delete(series)

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

    def get(self, entry):
        raise NotImplementedError


class PluginSeriesList(object):
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return SeriesListSet(config)

    def on_task_input(self, task, config):
        return list(SeriesListSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSeriesList, 'series_list', api_ver=2, groups=['list'])
