from __future__ import unicode_literals, division, absolute_import
import glob
import logging
import os
import urllib
import urlparse
import os.path

from sqlalchemy import Column, Integer, String, ForeignKey, or_, and_, DateTime, Boolean
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import Table

from datetime import datetime, date, time
from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import with_session
from flexget.utils.template import RenderError
from flexget.utils.tools import parse_timedelta

try:
    from babelfish import Language
except ImportError:
    raise plugin.DependencyError(issued_by='subtitle_queue', missing='babelfish',
                                 message='subtitle_queue requires the babelfish plugin')

log = logging.getLogger('subtitle_queue')
Base = db_schema.versioned_base('subtitle_queue', 0)


#: Video extensions stolen from https://github.com/Diaoul/subliminal/blob/master/subliminal/video.py
VIDEO_EXTENSIONS = ('.3g2', '.3gp', '.3gp2', '.3gpp', '.60d', '.ajp', '.asf', '.asx', '.avchd', '.avi', '.bik',
                    '.bix', '.box', '.cam', '.dat', '.divx', '.dmf', '.dv', '.dvr-ms', '.evo', '.flc', '.fli',
                    '.flic', '.flv', '.flx', '.gvi', '.gvp', '.h264', '.m1v', '.m2p', '.m2ts', '.m2v', '.m4e',
                    '.m4v', '.mjp', '.mjpeg', '.mjpg', '.mkv', '.moov', '.mov', '.movhd', '.movie', '.movx', '.mp4',
                    '.mpe', '.mpeg', '.mpg', '.mpv', '.mpv2', '.mxf', '.nsv', '.nut', '.ogg', '.ogm', '.omf', '.ps',
                    '.qt', '.ram', '.rm', '.rmvb', '.swf', '.ts', '.vfw', '.vid', '.video', '.viv', '.vivo', '.vob',
                    '.vro', '.wm', '.wmv', '.wmx', '.wrap', '.wvx', '.wx', '.x264', '.xvid')


SUBTITLE_EXTENSIONS = ('.srt', '.sub', '.smi', '.txt', '.ssa', '.ass', '.mpl')  # Borrowed from Subliminal


association_table = Table('association', Base.metadata,
                          Column('sub_queue_id', Integer, ForeignKey('subtitle_queue.id')),
                          Column('lang_id', Integer, ForeignKey('subtitle_language.id'))
                          )


def normalize_path(path):
    return os.path.normcase(os.path.abspath(path)) if path else None


class SubtitleLanguages(Base):
    __tablename__ = 'subtitle_language'

    id = Column(Integer, primary_key=True)
    language = Column(String, unique=True, index=True)

    def __init__(self, language):
        self.language = unicode(Language.fromietf(language))

    def __str__(self):
        return '<SubtitleLanguage(%s)>' % self.language


class QueuedSubtitle(Base):

    __tablename__ = 'subtitle_queue'

    id = Column(Integer, primary_key=True)
    title = Column(String)  # Not completely necessary
    path = Column(String, unique=True, nullable=False)  # Absolute path of file to fetch subtitles for
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
        lang = None if not self.languages else self.languages[0]
        return '<SubtitleQueue(%s, %s, %s)>' % (self.path, self.added, lang)


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
                    'path': {'type': 'string'},
                    'alternate_path': {'type': 'string'},
                },
                'required': ['action'],
                'additionalProperties': False
            },
            {
                'type': 'string', 'enum': ['emit']
            },
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['emit']},
                    'remove_not_found': {'type': 'boolean', 'default': False},
                },
                'required': ['action'],
                'additionalProperties': False
            }
        ]
    }

    failed_paths = {}

    def prepare_config(self, config):
        if isinstance(config, basestring):
            config = {'action': config, 'remove_not_found': False}
        return config

    def on_task_start(self, task, config):
        self.failed_paths = {}

    def complete(self, entry, task=None, path=None, **kwargs):
        with Session() as session:
            item = session.query(QueuedSubtitle).filter(or_(QueuedSubtitle.path == path,
                                                            QueuedSubtitle.alternate_path == path)).first()
            if 'subtitles_missing' in entry and not entry['subtitles_missing']:
                entry.accept()
                if not self.failed_paths.get(path):
                    item.downloaded = True
            elif 'subtitles_missing' in entry:
                self.failed_paths[path] = True
                item.downloaded = False
                entry.fail()

    def emit(self, task, config):
        if not config:
            return
        entries = []
        with Session() as session:
            for sub_item in queue_get(session=session):
                if os.path.exists(sub_item.path):
                    path = sub_item.path
                elif sub_item.alternate_path and os.path.exists(sub_item.alternate_path):
                    path = sub_item.alternate_path
                elif not config['remove_not_found'] and \
                        sub_item.added + parse_timedelta('24 hours') > datetime.combine(date.today(), time()):
                    log.warning('File %s was not found. Deleting after %s.' %
                                (sub_item.path, unicode(sub_item.added + parse_timedelta('24 hours'))))
                    continue
                else:
                    log.error('File not found. Removing "%s" from queue.' % sub_item.title)
                    session.delete(sub_item)
                    continue
                if os.path.isdir(path):
                    paths = os.listdir(path)
                    if not paths:
                        log.warning('Queued folder %s is empty.' % path)
                        continue
                    path_dir = path
                else:
                    paths = [path]
                    path_dir = os.path.dirname(path)

                primary = set()
                for language in sub_item.languages:
                    primary.add(Language.fromietf(language.language))

                for file in paths:
                    entry = Entry()
                    if not file.lower().endswith(VIDEO_EXTENSIONS):
                        continue
                    file = normalize_path(os.path.join(path_dir, file))
                    entry['url'] = urlparse.urljoin('file:', urllib.pathname2url(file.encode('utf-8')))
                    entry['location'] = file
                    entry['title'] = os.path.splitext(os.path.basename(file))[0]  # filename without ext
                    entry['subtitle_languages'] = primary

                    try:
                        import subliminal
                        try:
                            video = subliminal.scan_video(normalize_path(file))
                            if primary and not primary - video.subtitle_languages:
                                log.debug('All subtitles already fetched for %s.' % entry['title'])
                                sub_item.downloaded = True
                                continue
                        except ValueError as e:
                            log.error('Invalid video file: %s. Removing %s from queue.' % (e, entry['title']))
                            session.delete(sub_item)
                            continue
                    except ImportError:
                        log.debug('Falling back to simple check since Subliminal is not installed.')
                        # use glob since subliminal is not there
                        path_no_ext = os.path.splitext(normalize_path(file))[0]
                        # can only check subtitles that have explicit language codes in the file name
                        if primary:
                            files = glob.glob(path_no_ext + "*")
                            files = [item.lower() for item in files]
                            for lang in primary:
                                if not any('%s.%s' % (path_no_ext, lang) and
                                           f.lower().endswith(SUBTITLE_EXTENSIONS) for f in files):
                                    break
                            else:
                                log.debug('All subtitles already fetched for %s.' % entry['title'])
                                sub_item.downloaded = True
                                continue
                    entry.on_complete(self.complete, path=path, task=task)
                    entries.append(entry)
                    log.debug('Emitting entry for %s.' % entry['title'])
        return entries

    def on_task_filter(self, task, config):
        config = self.prepare_config(config)
        if config['action'] is 'emit':
            for entry in task.entries:
                entry.accept()

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if config['action'] != 'emit':
            return
        return self.emit(task, config)

    def on_task_output(self, task, config):
        config = self.prepare_config(config)
        if not config or config['action'] is 'emit':
            return
        action = config.get('action')
        for entry in task.accepted:
            try:
                if action == 'add':
                    # is it a local file?
                    if 'location' in entry:
                        try:
                            path = entry.render(config.get('path', entry['location']))
                            alternate_path = entry.render(config.get('alternate_path', ''))
                            queue_add(path, entry.get('title', ''), config, alternate_path=alternate_path,
                                      location=entry['location'])
                        except RenderError as ex:
                            # entry.fail('Invalid entry field %s for %s.' % (config['path'], entry['title']))
                            log.error('Could not render: %s. Please check your config.' % ex)
                            break
                    # or is it a torrent?
                    elif 'torrent' in entry and 'content_files' in entry:
                        if 'path' not in config:
                            log.error('No path set for non-local file. Don\'t know where to look.')
                            break
                        # try to render
                        try:
                            path = entry.render(config['path'])
                            alternate_path = entry.render(config.get('alternate_path', ''))
                        except RenderError as ex:
                            # entry.fail('Invalid entry field %s for %s.' % (config['path'], entry['title']))
                            log.error('Could not render: %s. Please check your config.' % ex)
                            break
                        files = entry['content_files']
                        if len(files) == 1:
                            title = files[0]
                            # TODO: use content_filename in case of single-file torrents?
                            # How to handle path and alternate_path in this scenario?
                            ext = os.path.splitext(title)[1]
                            if 'content_filename' in entry:
                                # need to queue the content_filename as alternate
                                if not alternate_path:
                                    alternate_path = os.path.join(path, entry['content_filename'] + ext)
                                else:
                                    # if alternate_path already exists, then we simply change it
                                    alternate_path = os.path.join(alternate_path,
                                                                  entry['content_filename'] + ext)
                            else:
                                path = os.path.join(path, title)
                                if alternate_path:
                                    alternate_path = os.path.join(alternate_path, title)
                        else:
                            # title of the torrent is usually the name of the folder
                            title = entry['torrent'].content['info']['name']
                            path = os.path.join(path, title)
                            if alternate_path:
                                alternate_path = os.path.join(alternate_path, title)
                        queue_add(path, title, config, alternate_path=alternate_path)
                    else:
                        # should this really happen though?
                        entry.reject('Invalid entry. Not a torrent or local file.')
                elif action == 'remove':
                    if entry.get('location', ''):
                        queue_del(entry['location'])
                    else:
                        entry.reject('Not a local file. Cannot remove non-local files.')
            except QueueError as e:
                # ignore already in queue
                if e.errno != 1:
                    entry.fail('ERROR: %s' % e.message)


@with_session
def queue_add(path, title, config, alternate_path=None, location=None, session=None):
    path = normalize_path(path)
    alternate_path = normalize_path(alternate_path)
    location = normalize_path(location)
    conditions = [QueuedSubtitle.path == path, QueuedSubtitle.alternate_path == path]
    if location:
        conditions.extend([QueuedSubtitle.path == location, QueuedSubtitle.alternate_path == location])

    item = session.query(QueuedSubtitle).filter(or_(*conditions)).first()
    primary = make_lang_list(config.get('languages', []), session=session)
    if item:
        log.info('%s: Already queued. Updating values.' % item.title)
        queue_edit(path, alternate_path, title, config, location=location, session=session)
    else:
        if config.get('stop_after', ''):
            item = QueuedSubtitle(path, alternate_path, title, stop_after=config.get('stop_after'))
        else:
            item = QueuedSubtitle(path, alternate_path, title)
        session.add(item)
        item.languages = primary
        log.info('Added %s to queue with langs: [%s].' %
                 (item.path, ', '.join([unicode(s.language) for s in item.languages])))
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
def queue_edit(src, dest, title, config, location=None, session=None):
    src = normalize_path(src)
    dest = normalize_path(dest)
    location = normalize_path(location)
    conditions = [QueuedSubtitle.path == src, QueuedSubtitle.alternate_path == src]
    if location:
        conditions.extend([QueuedSubtitle.path == location, QueuedSubtitle.alternate_path == location])

    item = session.query(QueuedSubtitle).filter(or_(*conditions)).first()

    # item should exist, but this check might be needed in the future
    if not item:
        # tried to edit a non-queued item. Add it.
        queue_add(dest, title, config, alternate_path=src, location=location, session=session)
    else:
        if item.downloaded:
            log.info('All subtitles have already been downloaded. Not updating values.')
            return
        if item.path != src:
            item.path = src
        if item.alternate_path != dest:
            item.alternate_path = dest
        # if there is a stop_after value, then it is refreshed in the db
        if config.get('stop_after', ''):
            item.stop_after = config['stop_after']
            item.added = datetime.now()
        if config.get('languages'):
            primary = make_lang_list(config.get('languages', []), session=session)
            item.languages = primary
        log.info('Updated values for %s.' % item.title)


@with_session
def queue_get(session=None):
    subs = session.query(QueuedSubtitle).filter(QueuedSubtitle.downloaded == False).all()
    # remove any items that have expired
    for sub_item in subs:
        if sub_item.added + parse_timedelta(sub_item.stop_after) < datetime.combine(date.today(), time()):
            log.debug('%s has expired. Removing.' % sub_item.title)
            subs.remove(sub_item)
            session.delete(sub_item)
    return subs


# must always pass the session
@with_session
def get_lang(lang, session=None):
    return session.query(SubtitleLanguages).filter(SubtitleLanguages.language == unicode(lang)).first()


@with_session
def make_lang_list(languages, session=None):
    if not isinstance(languages, list):
        languages = [languages]
    # TODO: find better way of enforcing uniqueness without catching exceptions or doing dumb shit like this
    languages = set([unicode(Language.fromietf(l)) for l in languages])

    result = set()
    for language in languages:
        lang = get_lang(language, session=session) or SubtitleLanguages(unicode(language))
        result.add(lang)
    return list(result)


class QueueError(Exception):
    """Exception raised if there is an error with a queue operation"""

    # TODO: taken from movie_queue
    def __init__(self, message, errno=0):
        self.message = message
        self.errno = errno


@event('plugin.register')
def register_plugin():
    plugin.register(SubtitleQueue, 'subtitle_queue', api_ver=2)
