import re
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='filesystem')


class Filesystem:
    """
    Uses local path content as an input. Can use recursion if configured.
    Recursion is False by default. Can be configured to true or get integer that will specify max depth in relation to
        base folder.
    All files/dir/symlinks are retrieved by default. Can be changed by using the 'retrieve' property.

    Example 1:: Single path

      filesystem: /storage/movies/

    Example 2:: List of paths

      filesystem:
         - /storage/movies/
         - /storage/tv/

    Example 3:: Object with list of paths

      filesystem:
        path:
          - /storage/movies/
          - /storage/tv/
        mask: '*.mkv'

    Example 4::

      filesystem:
        path:
          - /storage/movies/
          - /storage/tv/
        recursive: 4  # 4 levels deep from each base folder
        retrieve: files  # Only files will be retrieved

    Example 5::

      filesystem:
        path:
          - /storage/movies/
          - /storage/tv/
        recursive: yes  # No limit to depth, all sub dirs will be accessed
        retrieve:  # Only files and dirs will be retrieved
          - files
          - dirs

    """

    retrieval_options = ['files', 'dirs', 'symlinks']
    paths = one_or_more({'type': 'string', 'format': 'path'}, unique_items=True)

    schema = {
        'oneOf': [
            paths,
            {
                'type': 'object',
                'properties': {
                    'path': paths,
                    'mask': {'type': 'string'},
                    'regexp': {'type': 'string', 'format': 'regex'},
                    'recursive': {
                        'oneOf': [{'type': 'integer', 'minimum': 2}, {'type': 'boolean'}]
                    },
                    'retrieve': one_or_more(
                        {'type': 'string', 'enum': retrieval_options}, unique_items=True
                    ),
                },
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        from fnmatch import translate

        config = config

        # Converts config to a dict with a list of paths
        if not isinstance(config, dict):
            config = {'path': config}
        if not isinstance(config['path'], list):
            config['path'] = [config['path']]

        config.setdefault('recursive', False)
        # If mask was specified, turn it in to a regexp
        if config.get('mask'):
            config['regexp'] = translate(config['mask'])
        # If no mask or regexp specified, accept all files
        config.setdefault('regexp', '.')
        # Sets the default retrieval option to files
        config.setdefault('retrieve', self.retrieval_options)

        return config

    def create_entry(self, filepath: Path, test_mode):
        """
        Creates a single entry using a filepath and a type (file/dir)
        """
        filepath = filepath.absolute()
        entry = Entry()
        entry['location'] = str(filepath)
        entry['url'] = Path(filepath).absolute().as_uri()
        entry['filename'] = filepath.name
        if filepath.is_file():
            entry['title'] = filepath.stem
        else:
            entry['title'] = filepath.name
        file_stat = filepath.stat()
        try:
            entry['timestamp'] = datetime.fromtimestamp(file_stat.st_mtime)
        except Exception as e:
            logger.warning('Error setting timestamp for {}: {}', filepath, e)
            entry['timestamp'] = None
        entry['accessed'] = datetime.fromtimestamp(file_stat.st_atime)
        entry['modified'] = datetime.fromtimestamp(file_stat.st_mtime)
        entry['created'] = datetime.fromtimestamp(file_stat.st_ctime)
        if entry.isvalid():
            if test_mode:
                logger.info("Test mode. Entry includes:")
                logger.info(' Title: {}', entry['title'])
                logger.info(' URL: {}', entry['url'])
                logger.info(' Filename: {}', entry['filename'])
                logger.info(' Location: {}', entry['location'])
                logger.info(' Timestamp: {}', entry['timestamp'])
            return entry
        else:
            logger.error('Non valid entry created: {} ', entry)
            return

    def get_max_depth(self, recursion, base_depth):
        if recursion is False:
            return base_depth + 1
        elif recursion is True:
            return float('inf')
        else:
            return base_depth + recursion

    @staticmethod
    def get_folder_objects(folder: Path, recursion: bool):
        return folder.rglob('*') if recursion else folder.iterdir()

    def get_entries_from_path(
        self, path_list, match, recursion, test_mode, get_files, get_dirs, get_symlinks
    ):
        entries = []

        for folder in path_list:
            logger.verbose('Scanning folder {}. Recursion is set to {}.', folder, recursion)
            folder = Path(folder).expanduser()
            if not folder.exists():
                logger.error('{} does not exist (anymore.)', folder)
                continue
            logger.debug('Scanning {}', folder)
            base_depth = len(folder.parts)
            max_depth = self.get_max_depth(recursion, base_depth)
            folder_objects = self.get_folder_objects(folder, recursion)
            for path_object in folder_objects:
                logger.debug('Checking if {} qualifies to be added as an entry.', path_object)
                try:
                    path_object.exists()
                except UnicodeError:
                    logger.error(
                        'File {} not decodable with filesystem encoding: {}',
                        path_object,
                        sys.getfilesystemencoding(),
                    )
                    continue
                entry = None
                object_depth = len(path_object.parts)
                if object_depth <= max_depth:
                    if match(str(path_object)):
                        if (
                            (path_object.is_dir() and get_dirs)
                            or (path_object.is_symlink() and get_symlinks)
                            or (
                                path_object.is_file()
                                and not path_object.is_symlink()
                                and get_files
                            )
                        ):
                            entry = self.create_entry(path_object, test_mode)
                        else:
                            logger.debug(
                                "Path object's {} type doesn't match requested object types.",
                                path_object,
                            )
                        if entry and entry not in entries:
                            entries.append(entry)

        return entries

    def on_task_input(self, task, config):
        config = self.prepare_config(config)

        path_list = config['path']
        test_mode = task.options.test
        match = re.compile(config['regexp'], re.IGNORECASE).match
        recursive = config['recursive']
        get_files = 'files' in config['retrieve']
        get_dirs = 'dirs' in config['retrieve']
        get_symlinks = 'symlinks' in config['retrieve']

        logger.verbose('Starting to scan folders.')
        return self.get_entries_from_path(
            path_list, match, recursive, test_mode, get_files, get_dirs, get_symlinks
        )


@event('plugin.register')
def register_plugin():
    plugin.register(Filesystem, 'filesystem', api_ver=2)
