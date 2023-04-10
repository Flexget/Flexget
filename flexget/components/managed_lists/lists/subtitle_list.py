import os
from collections.abc import MutableSet
from datetime import date, datetime, time

from babelfish import Language
from loguru import logger
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Unicode, and_, func
from sqlalchemy.orm import relationship

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.template import RenderError
from flexget.utils.tools import parse_timedelta

logger = logger.bind(name='subtitle_list')
Base = versioned_base('subtitle_list', 1)

#: Video extensions stolen from https://github.com/Diaoul/subliminal/blob/master/subliminal/video.py
VIDEO_EXTENSIONS = (
    '.3g2',
    '.3gp',
    '.3gp2',
    '.3gpp',
    '.60d',
    '.ajp',
    '.asf',
    '.asx',
    '.avchd',
    '.avi',
    '.bik',
    '.bix',
    '.box',
    '.cam',
    '.dat',
    '.divx',
    '.dmf',
    '.dv',
    '.dvr-ms',
    '.evo',
    '.flc',
    '.fli',
    '.flic',
    '.flv',
    '.flx',
    '.gvi',
    '.gvp',
    '.h264',
    '.m1v',
    '.m2p',
    '.m2ts',
    '.m2v',
    '.m4e',
    '.m4v',
    '.mjp',
    '.mjpeg',
    '.mjpg',
    '.mkv',
    '.moov',
    '.mov',
    '.movhd',
    '.movie',
    '.movx',
    '.mp4',
    '.mpe',
    '.mpeg',
    '.mpg',
    '.mpv',
    '.mpv2',
    '.mxf',
    '.nsv',
    '.nut',
    '.ogg',
    '.ogm',
    '.omf',
    '.ps',
    '.qt',
    '.ram',
    '.rm',
    '.rmvb',
    '.swf',
    '.ts',
    '.vfw',
    '.vid',
    '.video',
    '.viv',
    '.vivo',
    '.vob',
    '.vro',
    '.wm',
    '.wmv',
    '.wmx',
    '.wrap',
    '.wvx',
    '.wx',
    '.x264',
    '.xvid',
)


def normalize_language(language):
    if isinstance(language, Language):
        return str(language)
    return str(Language.fromietf(language))


def normalize_path(path):
    return os.path.normpath(os.path.abspath(path)) if path else None


class SubtitleListList(Base):
    __tablename__ = 'subtitle_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    files = relationship(
        'SubtitleListFile', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic'
    )

    def __repr__(self):
        return '<SubtitleListList name=%s,id=%d>' % (self.name, self.id)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'added_on': self.added}


class SubtitleListFile(Base):
    __tablename__ = 'subtitle_list_files'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    location = Column(Unicode)
    list_id = Column(Integer, ForeignKey(SubtitleListList.id), nullable=False)
    languages = relationship(
        'SubtitleListLanguage', backref='file', lazy='joined', cascade='all, delete-orphan'
    )
    remove_after = Column(Unicode)

    def __repr__(self):
        return '<SubtitleListFile title={},path={},list_name={}>'.format(
            self.title,
            self.location,
            self.list.name,
        )

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
        subtitle_languages = [
            subtitle_list_language.language for subtitle_list_language in self.languages
        ]
        return {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'location': self.location,
            'subtitle_languages': subtitle_languages,
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
            'remove_after': {'type': 'string', 'format': 'interval'},
            'path': {'type': 'string'},
            'allow_dir': {'type': 'boolean', 'default': False},
            'recursion_depth': {'type': 'integer', 'default': 1, 'minimum': 1},
            'force_file_existence': {'type': 'boolean', 'default': True},
        },
        'required': ['list'],
        'additionalProperties': False,
    }

    def _db_list(self, session):
        return (
            session.query(SubtitleListList)
            .filter(SubtitleListList.name == self.config['list'])
            .first()
        )

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @with_session
    def __init__(self, config, session=None):
        self.config = config
        db_list = self._db_list(session)
        if not db_list:
            session.add(SubtitleListList(name=self.config['list']))

    def __iter__(self):
        with Session() as session:
            return iter([file.to_entry() for file in self._db_list(session).files])

    def __len__(self):
        with Session() as session:
            return self._db_list(session).files.count()

    def _extract_path(self, entry):
        path = ''
        if isinstance(self.config.get('path'), str):
            try:
                path = entry.render(self.config['path'])
            except RenderError as e:
                logger.error(e)
        else:
            path = entry.get('location')
        return normalize_path(path)

    def add(self, entry):
        with Session() as session:
            path = self._extract_path(entry)

            if not path:
                logger.error('Entry {} does not represent a local file/dir.', entry['title'])
                return

            path_exists = os.path.exists(path)
            if self.config['force_file_existence'] and not path_exists:
                logger.error('Path {} does not exist. Not adding to list.', path)
                return
            elif path_exists and not self.config.get('allow_dir') and os.path.isdir(path):
                logger.error(
                    'Path {} is a directory and "allow_dir"={}.', path, self.config['allow_dir']
                )
                return

            # Check if this is already in the list, refresh info if so
            db_list = self._db_list(session=session)
            db_file = self._find_entry(entry, session=session)
            # Just delete and re-create to refresh
            if db_file:
                session.delete(db_file)
            db_file = SubtitleListFile()
            db_file.title = entry['title']
            db_file.location = path
            db_file.languages = []
            db_file.remove_after = self.config.get('remove_after')
            db_file.languages = []
            normalized_languages = {
                normalize_language(subtitle_language)
                for subtitle_language in self.config.get('languages', [])
            }
            for subtitle_language in normalized_languages:
                language = SubtitleListLanguage(language=subtitle_language)
                db_file.languages.append(language)
            logger.debug('adding entry {} with languages {}', entry, normalized_languages)
            db_list.files.append(db_file)
            session.commit()
            return db_file.to_entry()

    def discard(self, entry):
        with Session() as session:
            db_file = self._find_entry(entry, session=session)
            if db_file:
                logger.debug('deleting file {}', db_file)
                session.delete(db_file)

    def __contains__(self, entry):
        return self._find_entry(entry, match_file_to_dir=True) is not None

    @with_session
    def _find_entry(self, entry, match_file_to_dir=False, session=None):
        """Finds `SubtitleListFile` corresponding to this entry, if it exists."""
        path = self._extract_path(entry)
        res = self._db_list(session).files.filter(SubtitleListFile.location == path).first()
        if not res and match_file_to_dir:
            path = os.path.dirname(path)
            res = self._db_list(session).files.filter(SubtitleListFile.location == path).first()
        return res

    @with_session
    def _find_language(self, file_id, language, session=None):
        res = (
            session.query(SubtitleListLanguage)
            .filter(
                and_(
                    func.lower(SubtitleListLanguage.language) == str(language).lower(),
                    SubtitleListLanguage.subtitle_list_file_id == file_id,
                )
            )
            .first()
        )
        return res

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    @with_session
    def get(self, entry, session):
        match = self._find_entry(entry=entry, session=session)
        return match.to_entry() if match else None


class PluginSubtitleList:
    """Subtitle list"""

    schema = SubtitleList.schema

    @staticmethod
    def get_list(config):
        return SubtitleList(config)

    def all_subtitles_exist(self, file, wanted_languages):
        try:
            import subliminal

            existing_subtitles = set(subliminal.core.search_external_subtitles(file).values())
            if wanted_languages and len(wanted_languages - existing_subtitles) == 0:
                logger.info('Local subtitle(s) already exists for {}.', file)
                return True
            return False
        except ImportError:
            logger.warning('Subliminal not found. Unable to check for local subtitles.')

    def on_task_input(self, task, config):
        subtitle_list = SubtitleList(config)
        recursion_depth = config['recursion_depth']
        # A hack to not output certain files without deleting them from the list
        temp_discarded_items = set()
        for item in subtitle_list:
            if not config['force_file_existence'] and not os.path.exists(item['location']):
                logger.error('File {} does not exist. Skipping.', item['location'])
                temp_discarded_items.add(item)
                continue
            if not os.path.exists(item['location']):
                logger.error('File {} does not exist. Removing from list.', item['location'])
                subtitle_list.discard(item)
                continue
            if self._expired(item, config):
                logger.info(
                    'File {} has been in the list for {}. Removing from list.',
                    item['location'],
                    item['remove_after'] or config['remove_after'],
                )
                subtitle_list.discard(item)
                continue

            languages = set(item['subtitle_languages']) or set(config.get('languages', []))
            num_potential_files = 0
            num_added_files = 0
            if os.path.isdir(item['location']):
                # recursion depth 1 is no recursion
                max_depth = (
                    len(normalize_path(item['location']).split(os.sep)) + recursion_depth - 1
                )
                for root_dir, _, files in os.walk(item['location']):
                    current_depth = len(root_dir.split(os.sep))
                    if current_depth > max_depth:
                        break
                    for file in files:
                        if os.path.splitext(file)[1] not in VIDEO_EXTENSIONS:
                            logger.debug('File {} is not a video file. Skipping', file)
                            continue
                        num_potential_files += 1
                        file_path = normalize_path(os.path.join(root_dir, file))
                        if not config['check_subtitles'] or not self.all_subtitles_exist(
                            file_path, languages
                        ):
                            subtitle_list.config['languages'] = languages
                            subtitle_list.add(
                                Entry(
                                    title=os.path.splitext(os.path.basename(file_path))[0],
                                    url='file://' + file_path,
                                    location=file_path,
                                )
                            )
                            num_added_files += 1
                # delete the original dir if it contains any video files
                if num_added_files or num_potential_files:
                    logger.debug(
                        'Added {} file(s) from {} to subtitle list {}',
                        num_added_files,
                        item['location'],
                        config['list'],
                    )
                    subtitle_list.discard(item)
                else:
                    logger.debug('No files found in {}. Skipping.', item['location'])
                    temp_discarded_items.add(item)
            elif config['check_subtitles'] and self.all_subtitles_exist(
                item['location'], languages
            ):
                subtitle_list.discard(item)

        return list(set(subtitle_list) - temp_discarded_items)

    @classmethod
    def _expired(cls, file, config):
        added_interval = datetime.combine(date.today(), time()) - file['added']
        if file['remove_after'] and added_interval > parse_timedelta(file['remove_after']):
            return True
        elif config.get('remove_after') and added_interval > parse_timedelta(
            config['remove_after']
        ):
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSubtitleList, 'subtitle_list', api_ver=2, interfaces=['task', 'list'])
