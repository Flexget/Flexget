import logging
import re
from datetime import datetime

from sqlalchemy import Table, Column, Integer, ForeignKey, Index, Unicode, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from flexget import db_schema
from flexget.utils.sqlalchemy_utils import table_schema, get_index_by_name

log = logging.getLogger('archive.db')

SCHEMA_VER = 0

Base = db_schema.versioned_base('archive', SCHEMA_VER)

archive_tags_table = Table(
    'archive_entry_tags',
    Base.metadata,
    Column('entry_id', Integer, ForeignKey('archive_entry.id')),
    Column('tag_id', Integer, ForeignKey('archive_tag.id')),
    Index('ix_archive_tags', 'entry_id', 'tag_id'),
)

archive_sources_table = Table(
    'archive_entry_sources',
    Base.metadata,
    Column('entry_id', Integer, ForeignKey('archive_entry.id')),
    Column('source_id', Integer, ForeignKey('archive_source.id')),
    Index('ix_archive_sources', 'entry_id', 'source_id'),
)

Base.register_table(archive_tags_table)
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
    sources = relationship(
        "ArchiveSource", secondary=archive_sources_table, backref='archive_entries'
    )

    def __init__(self):
        self.added = datetime.now()

    def __str__(self):
        return '<ArchiveEntry(title=%s,url=%s,task=%s,added=%s)>' % (
            self.title,
            self.url,
            self.task,
            self.added.strftime('%Y-%m-%d %H:%M'),
        )


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
        new_index = get_index_by_name(
            Base.metadata.tables['archive_entry'], 'ix_archive_title_url'
        )
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
