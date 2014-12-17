from __future__ import unicode_literals, division, absolute_import
import glob
import logging
import os
import urllib
import urlparse
import posixpath

from sqlalchemy import Column, Integer, String, ForeignKey, or_, and_, DateTime, Boolean
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import Table

from datetime import datetime, date, time
from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.task import TaskAbort
from flexget.utils.database import with_session
from flexget.utils.tools import parse_timedelta

try:
    from babelfish import Language
except ImportError:
    raise plugin.DependencyError(issued_by='subtitle_queue', missing='babelfish',
                                 message='subtitle_queue requires the babelfish plugin')

log = logging.getLogger('subtitle_queue')
Base = db_schema.versioned_base('subtitle_queue', 0)


association_table = Table('association', Base.metadata,
                          Column('sub_queue_id', Integer, ForeignKey('subtitle_queue.id')),
                          Column('lang_id', Integer, ForeignKey('subtitle_language.id'))
                          )


def normalize_path(path):
    return os.path.normcase(os.path.abspath(path))


class SubtitleLanguages(Base):
    __tablename__ = 'subtitle_language'

    id = Column(Integer, primary_key=True)
    language = Column(String, unique=True, index=True)

    def __init__(self, language):
        self.language = unicode(Language.fromietf(language))

    def __str__(self):
        return '<SubtitleLanguage(%s)>' % (self.language)


class QueuedSubtitle(Base):

    __tablename__ = 'subtitle_queue'

    id = Column(Integer, primary_key=True)
    title = Column(String)  # Not completely necessary
    path = Column(String, unique=True)  # Absolute path of file to fetch subtitles for
    alternate_path = Column(String, unique=True)  # Absolute path of file to fetch subtitles for
    added = Column(DateTime)  # Used to determine age
    stop_after = Column(String)
    downloaded = Column(Boolean)
    languages = relationship(SubtitleLanguages, secondary=association_table, backref="primary", lazy='joined')

    def __init__(self, path, alternate_path, title, stop_after="7 days"):
        self.path = normalize_path(path)
        if alternate_path:
            self.alternate_path = normalize_path(alternate_path)
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
                    'action': {'type': 'string', 'enum': ['add', 'remove']},
                    'stop_after': {'type': 'string', 'format': 'interval'},
                    'languages': {"oneOf": [
                        {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
                        {'type': 'string'},
                    ]},
                    'primary_path': {'type': 'string'},
                    'alternate_path': {'type': 'string'},
                },
                'required': ['action'],
                'additionalProperties': False
            },
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['emit']}
                },
                'required': ['action'],
                'additionalProperties': False
            }
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
                log.info('%s: File not found. Retrying later.' % sub_item.path)
                continue
            elif sub_item.alternate_path:
                log.info('%s: File not found. Retrying later.' % sub_item.alternate_path)
                continue
            else:
                log.error('Bad entry. No paths specified.')
                continue
            entry['url'] = urlparse.urljoin('file:', urllib.pathname2url(path))
            entry['location'] = path
            entry['title'] = sub_item.title

            primary = []
            for language in sub_item.languages:
                primary.append(Language.fromietf(language.language))
            entry['subtitle_languages'] = primary

            # get the file extension index
            # use glob instead of subtitles_check as subtitles_check does some unnecessary hashing
            path = normalize_path(path)
            index = path.rfind('.')
            # if entry wants more than 1 subtitle, then we look for files that have the proper language extensions
            if len(primary) > 1:
                for lang in primary:
                    if not glob.glob(path[:index] + "." + unicode(lang) + ".srt"):
                        break
                else:
                    log.debug('All subtitles already fetched for %s.' % entry['title'])
                    continue
            # if entry wants only 1 subtitle, then we look for files with and without language extension
            else:
                if glob.glob(path[:index] + ".srt") or glob.glob(path[:index] + "." + unicode(primary[0]) + ".srt"):
                    log.debug('All primary subtitles already fetched for %s.' % entry['title'])
                    continue

            entries.append(entry)
            log.debug('Emitting subtitle entry for %s.' % entry['title'])
        return entries

    def on_task_filter(self, task, config):
        if config and config.get('action') == 'emit':
            for entry in task.entries:
                entry.accept()

    def on_task_input(self, task, config):
        if not config or config.get('action') != 'emit':
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
                    if 'location' in entry:
                        path = entry.render(config.get('primary_path', entry['location']))
                        alternate_path = entry.render(config.get('alternate_path', ''))
                        queue_add(path, entry.get('title', ''), config, alternate_path=alternate_path)
                    # or is it a torrent?
                    elif 'content_files' in entry:
                        path = entry.render(config.get('primary_path', ''))
                        if not path:
                            entry.reject('No path set for torrent. I am not a wizard. Please tell me where to look.')
                            break
                        alternate_path = entry.render(config.get('alternate_path', ''))
                        files = entry['content_files']
                        if len(files) == 1:
                            title = files[0]
                            # TODO: use content_filename in case of single-file torrents?
                            # How to handle path and alternate_path in this scenario?
                            alternate_title = title
                            if 'content_filename' in entry:
                                # need to queue the content_filename as alternate
                                ext = title.rfind('.')
                                alternate_title = os.path.join(entry['content_filename'], title[ext:])
                        else:
                            title = entry['title']
                            alternate_title = title
                        path = posixpath.join(path, title)

                        if alternate_path:
                            alternate_path = posixpath.join(alternate_path, alternate_title)

                        queue_add(path, title, config, alternate_path=alternate_path)
                    else:
                        #log.error("Invalid entry for subtitle queue.")
                        entry.fail('Invalid entry.')
                elif action == "remove":
                    if entry.get('location', ''):
                        queue_del(entry['location'])
                    else:
                        entry.fail('Not a local file.')
                return
            except QueueError as e:
                # ignore already in queue
                if e.errno != 1:
                    entry.fail("ERROR: %s" % e.message)


@with_session
def queue_add(path, title, config, alternate_path=None, session=None):
    path = normalize_path(path)
    if alternate_path:
        alternate_path = normalize_path(alternate_path)
    item = session.query(QueuedSubtitle).filter(or_(QueuedSubtitle.path == path,
                                                    QueuedSubtitle.alternate_path == path)).first()
    primary = make_lang_list(config.get('languages', []), session=session)
    eng = session.query(SubtitleLanguages).filter(SubtitleLanguages.language == 'en').first()
    default = [eng] if eng else [SubtitleLanguages('eng')]
    if item:
        log.debug('%s: Already queued. Updating values.' % item.title)
        queue_edit(path, alternate_path, title, config, session=session)
    else:
        if config.get('stop_after', ''):
            item = QueuedSubtitle(path, alternate_path, title, stop_after=config.get('stop_after'))
        else:
            item = QueuedSubtitle(path, alternate_path, title)
        session.add(item)
        item.languages = primary if primary else default
        log.info('Added %s to queue with %s primary languages.' % (item.path, len(item.languages)))
        return True


@with_session
def queue_del(path, session=None):
    path = normalize_path(path)
    item = session.query(QueuedSubtitle).filter(or_(QueuedSubtitle.path == path,
                                                    QueuedSubtitle.alternate_path == path)).first()
    if not item:
        # Not necessarily an error?
        raise QueueError("Cannot remove %s, not in the queue." % path)
    else:
        log.debug('Removed %s.' % item.path)
        session.delete(item)
        return item.path


@with_session
def queue_edit(src, dest, title, config, session=None):
    src = normalize_path(src)
    if dest:
        dest = normalize_path(dest)

    item = session.query(QueuedSubtitle).filter(QueuedSubtitle.path == src).first()
    if not item:
        # Two paths but not in queue could mean it comes from a torrent or has been moved with move plugin etc.
        queue_add(dest, title, config, alternate_path=src, session=session)
    else:
        if src:
            item.path = src
        if dest:
            item.alternate_path = dest
        # if there is a stop_after value, then it is refreshed in the db
        if config.get('stop_after', ''):
            item.stop_after = config['stop_after']
        primary = make_lang_list(config.get('languages', []), session=session)
        item.languages = primary


@with_session
def queue_get(session=None):
    subs = session.query(QueuedSubtitle).all()
    # remove any items that have expired
    for sub_item in subs:
        if sub_item.added + parse_timedelta(sub_item.stop_after) < datetime.combine(date.today(), time()):
            subs.remove(sub_item)
            session.delete(sub_item)
    return subs


# must always pass the session
@with_session
def get_lang(lang, session=None):
    return session.query(SubtitleLanguages).filter(SubtitleLanguages.language == unicode(lang)).first()


# TODO: prettify? ugly shit code fuck me
@with_session
def make_lang_list(languages, session=None):
    primary = []
    if not isinstance(languages, list):
        languages = [languages]
    # TODO: find better way of enforcing uniqueness without catching exceptions or doing dumb shit like this
    languages = set([unicode(Language.fromietf(l)) for l in languages])

    for language in languages:
        l = get_lang(language, session=session)
        if l and l not in primary:
            primary.append(l)
        else:
            l = SubtitleLanguages(unicode(language))
            primary.append(l)

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