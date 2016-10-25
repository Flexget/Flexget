from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from collections import MutableSet
from datetime import datetime
from flexget.db_schema import versioned_base
from sqlalchemy import Column, Unicode, select, Integer, DateTime, or_, func
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

log = logging.getLogger('series_list')
Base = versioned_base('series_list', 0)


class SeriesListList(Base):
    __tablename__ = 'series_list_lists'

    id = Column(Integer, primary_key=True)
    list_name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    series = relationship('Series', backref='series_list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __init__(self, list_name):
        self.list_name = list_name

    def to_dict(self):
        return {
            'id': self.id,
            'list_name': self.list_name,
            'added_on': self.added
        }
