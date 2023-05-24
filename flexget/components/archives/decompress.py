import os
import re

from loguru import logger

from flexget import plugin
from flexget.components.archives import utils as archiveutil
from flexget.event import event
from flexget.utils.template import RenderError, render_from_entry

logger = logger.bind(name='decompress')


def fail_entry_with_error(entry, error):
    """
    Log error message at error level and fail the entry
    """
    logger.error(error)
    entry.fail(error)


def open_archive_entry(entry):
    """
    Convenience function for opening archives from entries. Returns an archive.Archive object
    """
    archive_path = entry.get('location', '')
    if not archive_path:
        logger.error('Entry does not appear to represent a local file.')
        return
    if not os.path.exists(archive_path):
        logger.error('File no longer exists: {}', entry['location'])
        return
    try:
        archive = archiveutil.open_archive(archive_path)
    except archiveutil.BadArchive as error:
        fail_entry_with_error(entry, f'Bad archive: {archive_path} ({error})')
    except archiveutil.NeedFirstVolume:
        logger.error('Not the first volume: {}', archive_path)
    except archiveutil.ArchiveError as error:
        fail_entry_with_error(entry, f'Failed to open Archive: {archive_path} ({error})')
    else:
        return archive


def get_output_path(to, entry):
    """Determine which path to output to"""
    try:
        if to:
            return render_from_entry(to, entry)
        else:
            return os.path.dirname(entry.get('location'))
    except RenderError:
        raise plugin.PluginError('Could not render path: %s' % to)


def extract_info(info, archive, to, keep_dirs, test=False):
    """Extract ArchiveInfo object"""

    destination = get_destination_path(info, to, keep_dirs)

    if test:
        logger.info('Would extract: {} to {}', info.filename, destination)
        return
    logger.debug('Attempting to extract: {} to {}', info.filename, destination)
    try:
        info.extract(archive, destination)
    except archiveutil.FSError as error:
        logger.error('OS error while creating file: {} ({})', destination, error)
    except archiveutil.FileAlreadyExists:
        logger.warning('File already exists: {}', destination)
    except archiveutil.ArchiveError as error:
        logger.error('Failed to extract file: {} from {} ({})', info.filename, archive.path, error)


def get_destination_path(info, to, keep_dirs):
    """Generate the destination path for a given file"""

    path_suffix = info.path if keep_dirs else os.path.basename(info.path)

    return os.path.join(to, path_suffix)


def is_match(info, pattern):
    """Returns whether an info record matches the supplied regex"""
    match = re.compile(pattern, re.IGNORECASE).match
    is_match = bool(match(info.filename))

    if is_match:
        logger.debug('Found matching file: {}', info.filename)
    else:
        logger.debug('File did not match regexp: {}', info.filename)

    return is_match


class Decompress:
    r"""
    Extracts files from Zip or RAR archives. By default this plugin will extract to the same
    directory as the source archive, preserving directory structure from the archive.

    This plugin requires the rarfile Python module and unrar command line utility to extract RAR
    archives.

    Configuration:

    to:                 Destination path; supports Jinja2 templating on the input entry. Fields such
                        as series_name must be populated prior to input into this plugin using
                        metainfo_series or similar. If no path is specified, archive contents will
                        be extraced in the same directory as the archve itself.
    keep_dirs:          [yes|no] (default: yes) Indicates whether to preserve the directory
                        structure from within the archive in the destination path.
    mask:               Shell-style file mask; any matching files will be extracted. When used, this
                        field will override regexp.
    regexp:             Regular expression pattern; any matching files will be extracted. Overridden
                        by mask if specified.
    unrar_tool:         Specifies the path of the unrar tool. Only necessary if its location is not
                        defined in the operating system's PATH environment variable.
    delete_archive:     [yes|no] (default: no) Delete this archive after extraction is completed.


    Example:

      decompress:
        to: '/Volumes/External/TV/{{series_name}}/Season {{series_season}}/'
        keep_dirs: yes
        regexp: '.*s\d{1,2}e\d{1,2}.*\.mkv'
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'to': {'type': 'string'},
                    'keep_dirs': {'type': 'boolean'},
                    'mask': {'type': 'string'},
                    'regexp': {'type': 'string', 'format': 'regex'},
                    'unrar_tool': {'type': 'string'},
                    'delete_archive': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ]
    }

    @staticmethod
    def prepare_config(config):
        """Prepare config for processing"""
        from fnmatch import translate

        if not isinstance(config, dict):
            config = {}

        config.setdefault('to', '')
        config.setdefault('keep_dirs', True)
        config.setdefault('unrar_tool', '')
        config.setdefault('delete_archive', False)

        # If mask was specified, turn it in to a regexp
        if 'mask' in config:
            config['regexp'] = translate(config['mask'])
        # If no mask or regexp specified, accept all files
        if 'regexp' not in config:
            config['regexp'] = '.'

        return config

    @staticmethod
    def handle_entry(entry, config, test=False):
        """
        Extract matching files into the directory specified

        Optionally delete the original archive if config.delete_archive is True
        """

        archive = open_archive_entry(entry)

        if not archive:
            return

        to = get_output_path(config['to'], entry)

        for info in archive.infolist():
            if is_match(info, config['regexp']):
                extract_info(info, archive, to, config['keep_dirs'], test=test)

        if config['delete_archive']:
            if not test:
                archive.delete()
            else:
                logger.info(f'Would delete archive {archive.path}')
                archive.close()
        else:
            archive.close()

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        try:
            archiveutil.RarArchive.check_import()
        except archiveutil.NeedRarFile as e:
            raise plugin.PluginError(e)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_output(self, task, config):
        """Task handler for archive_extract"""
        if isinstance(config, bool) and not config:
            return

        config = self.prepare_config(config)
        archiveutil.rarfile_set_tool_path(config)

        archiveutil.rarfile_set_path_sep(os.path.sep)

        for entry in task.accepted:
            self.handle_entry(entry, config, test=task.options.test)


@event('plugin.register')
def register_plugin():
    plugin.register(Decompress, 'decompress', api_ver=2)
