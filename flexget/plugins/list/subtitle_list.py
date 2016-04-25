from __future__ import unicode_literals, division, absolute_import
from builtins import *

import logging
from collections import MutableSet
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer, ForeignKey, func, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_
from sqlalchemy.schema import Table
from babelfish import Language

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.tools import split_title_year

log = logging.getLogger('movie_list')
Base = versioned_base('movie_list', 0)


association_table = Table('association', Base.metadata,
                          Column('subtitle_list_file_id', Integer, ForeignKey('subtitle_list_files.id')),
                          Column('subtitle_list_language_id', Integer, ForeignKey('subtitle_list_languages.id')))
Base.register_table(association_table)


def normalize_language(language):
    return str(Language.fromietf(language))


class SubtitleListList(Base):
    __tablename__ = 'subtitle_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    files = relationship('SubtitleListFile', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<SubtitleListList name=%d>' % (self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'added_on': self.added
        }


class SubtitleListFile(Base):
    __tablename__ = 'subtitle_list_files'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    location = Column(Unicode)
    list_id = Column(Integer, ForeignKey(SubtitleListList.id), nullable=False)
    languages = relationship('SubtitleListLanguage', backref='file', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<SubtitleListFile title=%s,path=%s,list_id=%d>' % (self.title, self.location, self.list_id)

    def to_entry(self):
        entry = Entry()
        entry['title'] = self.title
        entry['url'] = 'mock://localhost/subtitle_list/%d' % self.id
        entry['location'] = self.location
        entry['subtitle_languages'] = []
        for subtitle_language in self.languages:
            entry['subtitle_languages'].append(subtitle_language.language)
        return entry

    def to_dict(self):
        subtitle_languages = [subtitle_list_language.to_dict() for subtitle_list_language in self.languages]
        return {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'location': self.location,
            'subtitle_languages': subtitle_languages
        }


class SubtitleListLanguage(Base):
    __tablename__ = 'subtitle_list_languages'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    language = Column(Unicode)

    def __repr__(self):
        return '<SubtitleListLanguage id=%s,language=%s>' % (self.id, self.language)

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'language': self.language
        }


class SubtitleList(MutableSet):
    def _db_list(self, session):
        return session.query(SubtitleListList).filter(SubtitleListList.name == self.config['list']).first()

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @with_session
    def __init__(self, config, session=None):
        self.config = config
        db_list = self._db_list(session)
        if not db_list:
            session.add(SubtitleListList(name=self.config['list']))

    @with_session
    def __iter__(self, session=None):
        return iter([file.to_entry() for file in self._db_list(session).files])

    @with_session
    def __len__(self, session=None):
        return len(self._db_list(session).files)

    @with_session
    def add(self, entry, session=None):
        # Check if this is already in the list, refresh info if so
        db_list = self._db_list(session=session)
        db_file = self._find_entry(entry, session=session)
        # Just delete and re-create to refresh
        if db_file:
            session.delete(db_file)
        db_file = SubtitleListFile()
        db_file.title = entry['title']
        db_file.location = entry['location']
        for subtitle_language in self.config['languages']:
            normalized_language = normalize_language(subtitle_language)
            language = self._find_language(normalized_language)
            if not language:
                language = SubtitleListLanguage(language=normalized_language)
            db_file.languages.append(language)
        log.debug('adding entry %s', entry)
        db_list.files.append(db_file)
        session.commit()
        return db_file.to_entry()

    @with_session
    def discard(self, entry, session=None):
        db_file = self._find_entry(entry, session=session)
        if db_file:
            log.debug('deleting file %s', db_file)
            session.delete(db_file)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    @with_session
    def _find_entry(self, entry, session=None):
        """Finds `SubtitleListFile` corresponding to this entry, if it exists."""
        res = self._db_list(session).files.filter(SubtitleListFile.location == entry.get('location', '')).first()
        return res

    @with_session
    def _find_language(self, language, session=None):
        res = session.query(SubtitleListLanguage).filter(func.lower(SubtitleListLanguage.language) ==
                                                         str(language).lower()).first()
        return res

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False


class PluginSubtitleList(object):
    """Subtitle list"""
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return SubtitleList(config)

    def on_task_input(self, task, config):
        return list(SubtitleList(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubtitleList, 'subtitle_list', api_ver=2, groups=['list'])
