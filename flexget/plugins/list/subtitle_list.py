from __future__ import unicode_literals, division, absolute_import
from builtins import *

import logging
import os
from collections import MutableSet
from datetime import datetime, date, time

from sqlalchemy import Column, Unicode, Integer, ForeignKey, func, DateTime, and_
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Table
from babelfish import Language

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('subtitle_list')
Base = versioned_base('subtitle_list', 1)


def normalize_language(language):
    return str(Language.fromietf(language))


class SubtitleListList(Base):
    __tablename__ = 'subtitle_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    files = relationship('SubtitleListFile', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<SubtitleListList name=%s,id=%d>' % (self.name, self.id)

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
    languages = relationship('SubtitleListLanguage', backref='file', lazy='joined', cascade='all, delete-orphan')
    remove_after = Column(Unicode)

    def __repr__(self):
        return '<SubtitleListFile title=%s,path=%s,list_name=%s>' % (self.title, self.location, self.list.name)

    def to_entry(self):
        entry = Entry()
        entry['title'] = self.title
        entry['url'] = 'mock://localhost/subtitle_list/%d' % self.id
        entry['location'] = self.location
        entry['remove_after'] = self.remove_after
        entry['added'] = self.added
        entry['subtitle_languages'] = []
        for subtitle_language in self.languages:
            entry['subtitle_languages'].append(Language.fromietf(subtitle_language.language))
        return entry

    def to_dict(self):
        subtitle_languages = [subtitle_list_language.language for subtitle_list_language in self.languages]
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
    subtitle_list_file_id = Column(Integer, ForeignKey('subtitle_list_files.id'))


class SubtitleList(MutableSet):
    schema = {
        'type': 'object',
        'properties': {
            'list': {'type': 'string'},
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'check_subtitles': {'type': 'boolean', 'default': True},
            'remove_after': {'type': 'string', 'format': 'interval'}
        },
        'required': ['list'],
        'additionalProperties': False
    }

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
        return self._db_list(session).files.count()

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
        db_file.languages = []
        db_file.remove_after = self.config.get('remove_after')
        db_file.languages = []
        normalized_languages = {normalize_language(subtitle_language) for subtitle_language in
                                self.config.get('languages', [])}
        for subtitle_language in normalized_languages:
            normalized_language = normalize_language(subtitle_language)
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
    def _find_language(self, file_id, language, session=None):
        res = session.query(SubtitleListLanguage).filter(and_(
            func.lower(SubtitleListLanguage.language) == str(language).lower(),
            SubtitleListLanguage.subtitle_list_file_id == file_id)).first()
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


class PluginSubtitleList(object):
    """Subtitle list"""
    schema = SubtitleList.schema

    @staticmethod
    def get_list(config):
        return SubtitleList(config)

    def on_task_input(self, task, config):
        subtitle_list = SubtitleList(config)
        if config['check_subtitles']:
            for file in subtitle_list:
                if not os.path.isfile(file['location']):
                    log.error('File %s does not exist. Removing from list.', file['location'])
                    subtitle_list.discard(file)
                elif self._expired(file, config):
                    log.verbose('File %s has been in the list for %s. Removing from list.', file['location'],
                                file['remove_after'] or config['remove_after'])
                    subtitle_list.discard(file)
                else:
                    try:
                        import subliminal
                        existing_subtitles = set(subliminal.core.search_external_subtitles(file['location']).values())
                        wanted_languages = set(file['subtitle_languages']) or set(config.get('languages', []))
                        if wanted_languages and len(wanted_languages - existing_subtitles) == 0:
                            log.verbose('Local subtitle(s) already exists for %s. Removing from list.',
                                        file['location'])
                            subtitle_list.discard(file)
                    except ImportError:
                        log.warning('Subliminal not found. Unable to check for local subtitles.')

        return list(subtitle_list)

    @classmethod
    def _expired(cls, file, config):
        added_interval = datetime.combine(date.today(), time()) - file['added']
        if file['remove_after'] and added_interval > parse_timedelta(file['remove_after']):
            return True
        elif config.get('remove_after') and added_interval > parse_timedelta(config['remove_after']):
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubtitleList, 'subtitle_list', api_ver=2, groups=['list'])
