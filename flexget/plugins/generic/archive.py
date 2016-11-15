from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
from datetime import datetime

from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import Table, ForeignKey
from sqlalchemy import Column, Integer, DateTime, Unicode, Index

from flexget import db_schema, plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.sqlalchemy_utils import table_schema, get_index_by_name
from flexget.manager import Session

log = logging.getLogger('archive')

SCHEMA_VER = 0

Base = db_schema.versioned_base('archive', SCHEMA_VER)

archive_tags_table = Table('archive_entry_tags', Base.metadata,
                           Column('entry_id', Integer, ForeignKey('archive_entry.id')),
                           Column('tag_id', Integer, ForeignKey('archive_tag.id')),
                           Index('ix_archive_tags', 'entry_id', 'tag_id'))
Base.register_table(archive_tags_table)

archive_sources_table = Table('archive_entry_sources', Base.metadata,
                              Column('entry_id', Integer, ForeignKey('archive_entry.id')),
                              Column('source_id', Integer, ForeignKey('archive_source.id')),
                              Index('ix_archive_sources', 'entry_id', 'source_id'))
Base.register_table(archive_sources_table)


class ArchiveEntry(Base):
    __tablename__ = 'archive_entry'
    __table_args__ = (Index('ix_archive_title_url', 'title', 'url'),)

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    url = Column(Unicode, index=True)
    description = Column(Unicode)
    task = Column('feed', Unicode)  # DEPRECATED, but SQLite does not support drop column
    added = Column(DateTime, index=True)

    tags = relationship("ArchiveTag", secondary=archive_tags_table)
    sources = relationship("ArchiveSource", secondary=archive_sources_table, backref='archive_entries')

    def __init__(self):
        self.added = datetime.now()

    def __str__(self):
        return '<ArchiveEntry(title=%s,url=%s,task=%s,added=%s)>' % \
               (self.title, self.url, self.task, self.added.strftime('%Y-%m-%d %H:%M'))


class ArchiveTag(Base):
    __tablename__ = 'archive_tag'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, index=True)

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '<ArchiveTag(id=%s,name=%s)>' % (self.id, self.name)


class ArchiveSource(Base):
    __tablename__ = 'archive_source'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, index=True)

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '<ArchiveSource(id=%s,name=%s)>' % (self.id, self.name)


def get_source(name, session):
    """
    :param string name: Source name
    :param session: SQLAlchemy session
    :return: ArchiveSource from db or new one
    """
    try:
        return session.query(ArchiveSource).filter(ArchiveSource.name == name).one()
    except NoResultFound:
        source = ArchiveSource(name)
        return source


def get_tag(name, session):
    """
    :param string name: Tag name
    :param session: SQLAlchemy session
    :return: ArchiveTag from db or new one
    """
    try:
        return session.query(ArchiveTag).filter(ArchiveTag.name == name).one()
    except NoResultFound:
        source = ArchiveTag(name)
        return source


@db_schema.upgrade('archive')
def upgrade(ver, session):
    if ver is None:
        # get rid of old index
        aet = table_schema('archive_entry', session)
        old_index = get_index_by_name(aet, 'archive_feed_title')
        if old_index is not None:
            log.info('Dropping legacy index (may take a while) ...')
            old_index.drop()
            # create new index by title, url
        new_index = get_index_by_name(Base.metadata.tables['archive_entry'], 'ix_archive_title_url')
        if new_index:
            log.info('Creating new index (may take a while) ...')
            new_index.create(bind=session.connection())
        else:
            # maybe removed from the model by later migrations?
            log.error('Unable to create index `ix_archive_title_url`, removed from the model?')
            # TODO: nag about this ?
        # This is safe as long as we don't delete the model completely :)
        # But generally never use Declarative Models in migrate!
        if session.query(ArchiveEntry).first():
            log.critical('----------------------------------------------')
            log.critical('You should run `--archive consolidate` ')
            log.critical('one time when you have time, it may take hours')
            log.critical('----------------------------------------------')
        ver = 0
    return ver


class Archive(object):
    """
    Archives all new items into database where they can be later searched and injected.
    Stores the entries in the state as they are at the exit phase, this way task cleanup for title
    etc is stored into the database. This may however make injecting them back to the original task work
    wrongly.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'array', 'items': {'type': 'string'}}
        ]

    }

    def on_task_learn(self, task, config):
        """Add new entries into archive. We use learn phase in case the task corrects title or url via some plugins."""

        if isinstance(config, bool):
            tag_names = []
        else:
            tag_names = config

        tags = []
        for tag_name in set(tag_names):
            tags.append(get_tag(tag_name, task.session))

        count = 0
        processed = []
        for entry in task.entries + task.rejected + task.failed:
            # I think entry can be in multiple of those lists .. not sure though!
            if entry in processed:
                continue
            else:
                processed.append(entry)

            ae = task.session.query(ArchiveEntry). \
                filter(ArchiveEntry.title == entry['title']). \
                filter(ArchiveEntry.url == entry['url']).first()
            if ae:
                # add (missing) sources
                source = get_source(task.name, task.session)
                if source not in ae.sources:
                    log.debug('Adding `%s` into `%s` sources' % (task.name, ae))
                    ae.sources.append(source)
                # add (missing) tags
                for tag_name in tag_names:
                    atag = get_tag(tag_name, task.session)
                    if atag not in ae.tags:
                        log.debug('Adding tag %s into %s' % (tag_name, ae))
                        ae.tags.append(atag)
            else:
                # create new archive entry
                ae = ArchiveEntry()
                ae.title = entry['title']
                ae.url = entry['url']
                if 'description' in entry:
                    ae.description = entry['description']
                ae.task = task.name
                ae.sources.append(get_source(task.name, task.session))
                if tags:
                    # note, we're extending empty list
                    ae.tags.extend(tags)
                log.debug('Adding `%s` with %i tags to archive' % (ae, len(tags)))
                task.session.add(ae)
                count += 1
        if count:
            log.verbose('Added %i new entries to archive' % count)

    def on_task_abort(self, task, config):
        """
        Archive even on task abort, except if the abort has happened before session
        was started.
        """
        if task.session is not None:
            self.on_task_learn(task, config)


class UrlrewriteArchive(object):
    """
    Provides capability to rewrite urls from archive or make searches with discover.
    """

    entry_map = {'title': 'title',
                 'url': 'url',
                 'description': 'description'}

    schema = {'oneOf': [
        {'type': 'boolean'},
        {'type': 'array', 'items': {'type': 'string'}}
    ]}

    def search(self, task, entry, config=None):
        """Search plugin API method"""

        session = Session()
        entries = set()
        if isinstance(config, bool):
            tag_names = None
        else:
            tag_names = config
        try:
            for query in entry.get('search_strings', [entry['title']]):
                # clean some characters out of the string for better results
                query = re.sub(r'[ \(\)]+', ' ', query).strip()
                log.debug('looking for `%s` config: %s' % (query, config))
                for archive_entry in search(session, query, tags=tag_names, desc=True):
                    log.debug('rewrite search result: %s' % archive_entry)
                    entry = Entry()
                    entry.update_using_map(self.entry_map, archive_entry, ignore_none=True)
                    if entry.isvalid():
                        entries.add(entry)
        finally:
            session.close()
        log.debug('found %i entries' % len(entries))
        return entries


# API function, was also used from webui .. needs to be rethinked
def search(session, text, tags=None, sources=None, desc=False):
    """
    Search from the archive.

    :param string text: Search text, spaces and dots are tried to be ignored.
    :param Session session: SQLAlchemy session, should not be closed while iterating results.
    :param list tags: Optional list of acceptable tags
    :param list sources: Optional list of acceptable sources
    :param bool desc: Sort results descending
    :return: ArchiveEntries responding to query
    """
    keyword = str(text).replace(' ', '%').replace('.', '%')
    # clean the text from any unwanted regexp, convert spaces and keep dots as dots
    normalized_re = re.escape(text.replace('.', ' ')).replace('\\ ', ' ').replace(' ', '.')
    find_re = re.compile(normalized_re, re.IGNORECASE)
    query = session.query(ArchiveEntry).filter(ArchiveEntry.title.like('%' + keyword + '%'))
    if tags:
        query = query.filter(ArchiveEntry.tags.any(ArchiveTag.name.in_(tags)))
    if sources:
        query = query.filter(ArchiveEntry.sources.any(ArchiveSource.name.in_(sources)))
    if desc:
        query = query.order_by(ArchiveEntry.added.desc())
    else:
        query = query.order_by(ArchiveEntry.added.asc())
    for a in query.yield_per(5):
        if find_re.match(a.title):
            yield a
        else:
            log.trace('title %s is too wide match' % a.title)


@event('plugin.register')
def register_plugin():
    plugin.register(Archive, 'archive', api_ver=2)
    plugin.register(UrlrewriteArchive, 'flexget_archive', groups=['search'], api_ver=2)
