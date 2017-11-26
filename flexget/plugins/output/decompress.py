from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os
import re

from flexget import plugin
from flexget.event import event
from flexget.utils.template import render_from_entry, RenderError
from flexget.utils import archive

log = logging.getLogger('decompress')


def fail_entry_with_error(entry, error):
    """
    Log error message at error level and fail the entry
    """
    log.error(error)
    entry.fail(error)


def open_archive_entry(entry):
    """
    Convenience method for opening archives from entries. Returns an archive.Archive object
    """
    arch = None

    try:
        archive_path = entry['location']
        arch = archive.open_archive(archive_path)
    except KeyError:
        log.error('Entry does not appear to represent a local file.')
    except archive.BadArchive as error:
        fail_entry_with_error(entry, 'Bad archive: %s (%s)' % (archive_path, error))
    except archive.NeedFirstVolume:
        log.error('Not the first volume: %s', archive_path)
    except archive.ArchiveError as error:
        fail_entry_with_error(entry, 'Failed to open Archive: %s (%s)' % (archive_path, error))

    return arch


def get_destination_path(path, to, keep_dirs):
    """
    Generate the destination path for a given file
    """
    filename = os.path.basename(path)

    if keep_dirs:
        path_suffix = path
    else:
        path_suffix = filename

    return os.path.join(to, path_suffix)


def is_dir(info):
    """
    Tests whether the file descibed in info is a directory
    """

    if hasattr(info, 'isdir'):
        return info.isdir()
    else:
        base = os.path.basename(info.filename)
        return not base


def makepath(path):
    if not os.path.exists(path):
        log.debug('Creating path: %s', path)
        os.makedirs(path)


class Decompress(object):
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
                    'delete_archive': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        """
        Prepare config for processing
        """
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

    def handle_entry(self, entry, config):
        """
        Extract matching files into the directory specified

        Optionally delete the original archive if config.delete_archive is True
        """

        match = re.compile(config['regexp'], re.IGNORECASE).match
        archive_path = entry.get('location')
        if not archive_path:
            log.warning('Entry does not appear to represent a local file.')
            return
        archive_dir = os.path.dirname(archive_path)

        if not os.path.exists(archive_path):
            log.warning('File no longer exists: %s', archive_path)
            return

        arch = open_archive_entry(entry)

        if not arch:
            return

        to = config['to']
        if to:
            try:
                to = render_from_entry(to, entry)
            except RenderError as error:
                log.error('Could not render path: %s', to)
                entry.fail(str(error))
                return
        else:
            to = archive_dir

        for info in arch.infolist():
            destination = get_destination_path(info.filename, to, config['keep_dirs'])
            dest_dir = os.path.dirname(destination)
            arch_file = os.path.basename(info.filename)

            if is_dir(info):
                log.debug('Appears to be a directory: %s', info.filename)
                continue

            if not match(arch_file):
                log.debug('File did not match regexp: %s', arch_file)
                continue

            log.debug('Found matching file: %s', info.filename)

            log.debug('Creating path: %s', dest_dir)
            makepath(dest_dir)

            if os.path.exists(destination):
                log.verbose('File already exists: %s', destination)
                continue

            error_message = ''

            log.debug('Attempting to extract: %s to %s', arch_file, destination)
            try:
                arch.extract_file(info, destination)
            except archive.FSError as error:
                error_message = 'OS error while creating file: %s (%s)' % (destination, error)
            except archive.ArchiveError as error:
                error_message = 'Failed to extract file: %s in %s (%s)' % (info.filename,
                                                                           archive_path, error)

            if error_message:
                log.error(error_message)
                entry.fail(entry)

                if os.path.exists(destination):
                    log.debug('Cleaning up partially extracted file: %s', destination)
                    os.remove(destination)

                return

        if config['delete_archive']:
            arch.delete()
        else:
            arch.close()

    @plugin.priority(255)
    def on_task_output(self, task, config):
        """Task handler for archive_extract"""
        if isinstance(config, bool) and not config:
            return

        config = self.prepare_config(config)
        archive.rarfile_set_tool_path(config)

        archive.rarfile_set_path_sep(os.path.sep)

        for entry in task.accepted:
            self.handle_entry(entry, config)


@event('plugin.register')
def register_plugin():
    plugin.register(Decompress, 'decompress', api_ver=2)
