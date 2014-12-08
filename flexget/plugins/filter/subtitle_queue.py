from __future__ import unicode_literals, division, absolute_import
import glob
import logging
import os
import urllib
import urlparse
import flexget.bencode

from sqlalchemy import Column, Integer, String, ForeignKey, or_, and_, select, update, DateTime, Boolean, Unicode
from sqlalchemy.orm.exc import NoResultFound

from datetime import datetime, date, time
from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.task import TaskAbort
from flexget.utils import requests
from flexget.utils.database import quality_requirement_property, with_session
from flexget.utils.sqlalchemy_utils import table_exists, table_schema
from flexget.utils.tools import parse_timedelta
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import relation, backref, relationship
from sqlalchemy.schema import Table

try:
    from flexget.plugins.filter import queue_base
except ImportError:
    raise plugin.DependencyError(issued_by='subtitle_queue', missing='queue_base',
                                 message='subtitle_queue requires the queue_base plugin')
try:
    from flexget.plugins.metainfo.subtitles_check import MetainfoSubs
except ImportError:
    raise plugin.DependencyError(issued_by='subtitle_queue', missing='subtitles_check',
                                 message='subtitle_queue requires way of checking for subtitles')
try:
    from babelfish import Language
except ImportError:
    raise plugin.DependencyError(issued_by='subtitle_queue', missing='babelfish',
                                 message='subtitle_queue requires the babelfish plugin')

log = logging.getLogger('subtitle_queue')
Base = db_schema.versioned_base('subtitle_queue', 0)


class NormalizedComparator(Comparator):
    def operate(self, op, other):
        return op(self.__clause_element__(), os.path.normcase(os.path.normpath(other)))


class LangComparator(Comparator):
    def operate(self, op, other):
        return op(self.__clause_element__(), other)

association_table = Table('association', Base.metadata,
                          Column('sub_queue_id', Integer, ForeignKey('subtitle_queue.id')),
                          Column('lang_id', Integer, ForeignKey('subtitle_language.id'))
                          )


class SubtitleLanguages(Base):
    __tablename__ = 'subtitle_language'

    id = Column(Integer, primary_key=True)
    _language = Column('language', Unicode, unique=True, index=True)
    #queued_sub_id = Column(Integer, ForeignKey('subtitle_queue.id'))

    def name_setter(self, value):
        self._language = value

    def name_getter(self):
        return Language.fromietf(self._language)

    def lang_comparator(self):
        return LangComparator(self._language)

    language = hybrid_property(name_getter, name_setter)
    language.comparator(lang_comparator)

    def __init__(self, language):
        self.language = language

    def __str__(self):
        return '<SubtitleLanguage(%s)>' % (self.language)


class QueuedSubtitle(Base):

    __tablename__ = 'subtitle_queue'

    id = Column(Integer, primary_key=True)
    title = Column(String)  # Not completely necessary
    _path = Column('path', Unicode)  # Absolute path of file to fetch subtitles for
    _path_normalized = Column('path_normalized', Unicode, index=True, unique=True)
    _alternate_path = Column('alternate_path', Unicode)  # Absolute path of file to fetch subtitles for
    _alternate_path_normalized = Column('alternate_path_normalized', Unicode, index=True, unique=True)
    #imdb_id = Column(String)  # not sure this is strictly necessary
    added = Column(DateTime)  # Used to determine age
    stop_after = Column(String)
    downloaded = Column(Boolean)
    languages = relationship(SubtitleLanguages, secondary=association_table, backref="primary")

    def name_setter(self, value):
        self._path = value
        self._path_normalized = os.path.normcase(os.path.normpath(value))

    def name_getter(self):
        return self._path

    def name_comparator(self):
        return NormalizedComparator(self._path_normalized)

    path = hybrid_property(name_getter, name_setter)
    path.comparator(name_comparator)

    def alt_setter(self, value):
        self._alternate_path = value
        self._alternate_path_normalized = os.path.normcase(os.path.normpath(value)) if value is not None else None

    def alt_getter(self):
        return self._alternate_path

    def alt_comparator(self):
        return NormalizedComparator(self._alternate_path_normalized)

    alternate_path = hybrid_property(alt_getter, alt_setter)
    alternate_path.comparator(alt_comparator)

    def __init__(self, path, alternate_path, title, stop_after="7 days"):
        self.path = path
        self.alternate_path = alternate_path
        self.added = datetime.now()
        self.stop_after = stop_after
        self.title = title
        self.downloaded = False

    def __str__(self):
        return '<SubtitleQueue(%s, %s, %s)>' % (self.path, self.added, self.languages[0])


class SubtitleQueue(object):
    schema = {
        "oneOf": [
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['add', 'remove', 'emit']},
                    'stop_after': {'type': 'string', 'format': 'interval'},
                    'languages': {"oneOf": [
                        {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
                        {'type': 'string'},
                    ]},
                },
                'required': ['action'],
                'additionalProperties': False
            },
        ]
    }

    def emit(self, task, config):
        if not config:
            return
        subtitles = queue_get(session=task.session)
        entries = []
        for sub_item in subtitles:
            entry = Entry()
            if os.path.exists(sub_item.path):
                path = sub_item.path
            elif sub_item.alternate_path and os.path.exists(sub_item.alternate_path):
                path = sub_item.alternate_path
            elif sub_item.path:
                log.debug('%s: File not found.' % sub_item.path)
                continue
            elif sub_item.alternate_path:
                log.debug('%s: File not found.' % sub_item.alternate_path)
                continue
            else:
                log.error('Bad entry. No paths specified.')
                continue
            entry['url'] = urlparse.urljoin('file:', urllib.pathname2url(path))
            entry['location'] = path
            entry['title'] = sub_item.title

            primary = []
            for language in sub_item.languages:
                primary.append(language.language)
            entry['subtitle_languages'] = primary

            index = path.rfind('.')
            if len(primary) > 1:
                for lang in primary:
                    if not glob.glob(path[:index] + "." + str(lang) + ".srt"):
                        break
                else:
                    log.debug('All primary subtitles already fetched for %s.' % entry['title'])
                    continue
            else:
                if glob.glob(path[:index] + ".srt"):
                    log.debug('All primary subtitles already fetched for %s.' % entry['title'])
                    continue
            entries.append(entry)
            log.debug('Emitted subtitle entry for %s.' % entry['title'])
        return entries

    def on_task_filter(self, task, config):
        if config:
            for entry in task.entries:
                entry.accept()

    def on_task_input(self, task, config):
        if not config:
            return
        return self.emit(task, config)

    def on_task_output(self, task, config):
        if not config:
            return
        action = config.get('action')
        if action == 'emit':
            return
        for entry in task.accepted:
            try:
                if action == "add":
                    # is it a local file?
                    if os.path.isfile(entry.get('location', '')):
                        src = entry.get('location', '')
                        dest = entry.get('output', '')
                        if dest:
                            # file has been moved and original location may already be in db
                            queue_edit(src, dest, entry.get('title', ''), config)
                        else:
                            queue_add(src, entry.get('title', ''), config)
                    elif entry.get('url', '').endswith('.torrent'):
                        content_filename = entry.get('content_filename', '')
                        info = None
                        files = None
                        for url in entry.get('urls', ''):
                            try:
                                info = flexget.bencode.bdecode(requests.get(url).text)['info']
                                files = info['files']
                                break
                            except Exception:
                                continue
                        if not info or not files:
                            raise TaskAbort('Invalid entry. Cannot queue.')
                        if len(files) == 1:
                            title = files[0]['path'][0]  # extract file name
                            if content_filename:
                                # need to queue the content_filename
                                ext = title.rfind('.')
                                title = content_filename + title[ext:]
                        else:
                            # TODO: queue dir or specific files?
                            # paths = []
                            # for file in files:
                            #     p = file['path'][0]
                            #     # this is bad
                            #     if p.endswith(('.avi', '.mkv', '.mp4', '.mov', '.mpg', '.wmv')):
                            #         paths.append(p)
                            #

                            # set the title to be torrent name, which hopefully is download dir
                            title = info['name']
                        if entry.get('movedone', ''):
                            src = entry.get('path', '') + title
                            dest = entry.get('movedone', '') + title
                            queue_add(src, entry.get('title', ''), config, alternate_path=dest)
                        elif entry.get('path', ''):
                            queue_add(entry.get('path'), entry.get('title', ''), config)
                        else:
                            raise TaskAbort("Cannot queue invalid entries.")
                    else:
                        raise TaskAbort("Invalid entry for subtitle queue.")
                elif action == "remove":
                    if entry.get('location', ''):
                        queue_del(entry['location'])
                    else:
                        raise TaskAbort("Cannot delete non-local files.")
                return
            except QueueError as e:
                # ignore already in queue
                if e.errno != 1:
                    entry.fail("Error adding file to subtitle queue: %s" % e.message)


@with_session
def queue_add(path, title, config, alternate_path=None, session=None):
    path = unicode(path)
    item = session.query(QueuedSubtitle).filter(or_(QueuedSubtitle.path == path,
                                                    QueuedSubtitle.alternate_path == path)).first()
    primary = make_lang_list(config.get('languages', []), session=session)
    default = [SubtitleLanguages('eng')]
    if item:
        log.debug('Already queued. Updating values.')
        if item.path == path and alternate_path:
            item.alternate_path = alternate_path
        elif item.alternate_path == path and alternate_path:
            item.path = alternate_path
            #raise QueueError("ERROR: %s is already in the queue." % path, errno=1)
        item.languages = primary if primary else default
    else:
        if config.get('stop_after', ''):
            item = QueuedSubtitle(path, alternate_path, title, stop_after=config.get('stop_after'))
        else:
            item = QueuedSubtitle(path, alternate_path, title)
        session.add(item)
        item.languages = primary if primary else default
        log.debug('Added %s to queue with %s primary languages.' % (item.path, len(item.languages)))
        return True


@with_session
def queue_del(path, session=None):
    item = session.query(QueuedSubtitle).filter(or_(QueuedSubtitle.path == path,
                                                    QueuedSubtitle.alternate_path == path)).first()
    if not item:
        # Not necessarily an error?
        raise QueueError("DEBUG: %s is not in the queue." % path)
    else:
        session.delete(item)
        return item.path


@with_session
def queue_edit(src, dest, title, config, session=None):
    item = session.query(QueuedSubtitle).filter(QueuedSubtitle.path == src).first()
    if not item:
        log.debug("DEBUG: %s was moved but is not in the queue." % src)
        queue_add(dest, title, config, alternate_path=src, session=session)
        #raise QueueError("ERROR: %s is not in the queue." % src)
    else:
        item.alternate_path = src
        item.path = dest
        stop_after = config.get('stop_after', '')
        if stop_after and item.stop_after is not stop_after:
            item.stop_after = stop_after
        primary = make_lang_list(config.get('languages', []), session=session)
        item.languages = primary


@with_session
def queue_get(session=None):
    subs = session.query(QueuedSubtitle).all()
    for sub_item in subs:
        if sub_item.added + parse_timedelta(sub_item.stop_after) < datetime.combine(date.today(), time()):
            subs.remove(sub_item)
            session.delete(sub_item)
    return subs


# must always pass the session
@with_session
def get_lang(lang, session=None):
    l = session.query(SubtitleLanguages).filter(SubtitleLanguages.language == unicode(lang)).first()
    return l


# TODO: prettify? ugly shit code fuck me
@with_session
def make_lang_list(languages, session=None):
    primary = []
    if not isinstance(languages, list):
        languages = [languages]
    for language in languages:
        l = get_lang(language, session=session)
        if l:
            primary.append(l)
        else:
            primary.append(SubtitleLanguages(unicode(language)))
    return primary


class QueueError(Exception):
    """Exception raised if there is an error with a queue operation"""

    # TODO: taken from movie_queue
    def __init__(self, message, errno=0):
        self.message = message
        self.errno = errno


@event('plugin.register')
def register_plugin():
    plugin.register(SubtitleQueue, 'subtitle_queue', api_ver=2)