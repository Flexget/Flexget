from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import os
import re
import shutil
import zipfile

from flexget import plugin
from flexget.event import event
from flexget.utils.template import render_from_entry, RenderError

try:
    import rarfile
except ImportError:
    rarfile = None

log = logging.getLogger('decompress')

def set_rar_tool(config):
        unrar_tool = config['unrar_tool']

        if unrar_tool:
            if not rarfile:
                raise plugin.DependencyError(issued_by='decompress',
                                             missing='rarfile',
                                             message='rar_tool specified with no rarfile module installed.')
            else:
                rarfile.UNRAR_TOOL = unrar_tool
                log.debug('Set RarFile.unrar_tool to: %s', unrar_tool)

def open_archive(entry):
    """
    Returns the appropriate archive object
    """

    archive_path = entry['location']

    archive = None

    if zipfile.is_zipfile(archive_path):
            archive = zipfile.ZipFile(file=archive_path)
            log.debug('Successfully opened ZIP: %s', archive_path)
    elif rarfile and rarfile.is_rarfile(archive_path):
            archive = rarfile.RarFile(rarfile=archive_path)
            log.debug('Successfully opened RAR: %s', archive_path)
    else:
        if not rarfile:
            log.warning('Rarfile module not installed; unable to extract RAR archives.')

    return archive

def is_archive(entry):
    """
    Attempts to open an entry as an archive; returns True on success, False on failure.
    """

    archive = None
    ret = False

    try:
        archive = open_archive(entry)
        archive.close()
        ret = True
    except Exception as error:
        error_message = 'Failed to open file as archive: %s (%s)' % (entry['location'], error)
        log.debug(error_message)

    return ret

def is_dir(info):
    """
    Tests whether the file descibed in info is a directory
    """

    if hasattr(info, 'isdir'):
        return info.isdir()
    else:
        base = os.path.basename(info.filename)
        return not base

class FilterArchives(object):
    """
    Accepts entries that are valid Zip or RAR archives

    This plugin requires the rarfile Python module and unrar command line utility to handle RAR
    archives.

    Configuration:

    unrar_tool:         Specifies the path of the unrar tool. Only necessary if its location is not
                        defined in the operating system's PATH environment variable.
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'unrar_tool': {'type': 'string'},
                },
                'additionalProperties': False
            }
        ]
    }


    def prepare_config(self, config):
        """
        Prepare config for processing
        """

        if not isinstance(config, dict):
            config = {}

        config.setdefault('unrar_tool', '')

        return config

    @plugin.priority(200)
    def on_task_filter(self, task, config):
        """
        Task handler for is_archive
        """
        if isinstance(config, bool) and not config:
            return

        config = self.prepare_config(config)
        set_rar_tool(config)

        for entry in task.entries:
            if is_archive(entry):
                entry.accept()
            else:
                entry.reject()


class Decompress(object):
    """
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
            log.warning('Entry does not appear to represent a local file, decompress plugin only supports local files')
            return
        archive_dir = os.path.dirname(archive_path)
        archive_file = os.path.basename(archive_path)

        if not os.path.exists(archive_path):
            log.warning('File no longer exists: %s', archive_path)
            return

        try:
            archive = open_archive(entry)
        except (zipfile.BadZipfile, rarfile.BadRarFile):
            error_message = 'Bad archive: %s' % entry['location']
            log.error(error_message)
            entry.fail(error_message)
        except rarfile.NeedFirstVolume:
            log.error('Not the first volume: %s', entry['location'])
        except Exception as error:
            error_message = 'Failed to open Archive: %s (%s)' % (entry['location'], error)
            log.error(error_message)
            entry.fail(error_message)        

        if not archive:
            return

        to = config['to']
        if to:
            try:
                to = render_from_entry(to, entry)
            except RenderError as e:
                log.error('Could not render path: %s', to)
                entry.fail(e)
                return
        else:
            to = archive_dir

        for info in archive.infolist():
            path = info.filename
            filename = os.path.basename(path)

            if is_dir(info):
                log.debug('Appears to be a directory: %s', path)
                continue

            if not match(path):
                log.debug('File did not match regexp: %s', path)
                continue

            log.debug('Found matching file: %s', path)

            if config['keep_dirs']:
                path_suffix = path
            else:
                path_suffix = filename
            destination = os.path.join(to, path_suffix)
            dest_dir = os.path.dirname(destination)

            if not os.path.exists(dest_dir):
                log.debug('Creating path: %s', dest_dir)
                os.makedirs(dest_dir)

            if not os.path.exists(destination):
                success = False
                error_message = ''
                source = None

                log.debug('Attempting to extract: %s to %s', path, destination)
                try:
                    # python 2.6 doesn't seem to like "with" in conjuntion with ZipFile.open
                    source = archive.open(path)
                    with open(destination, 'wb') as target:
                        shutil.copyfileobj(source, target)

                    log.verbose('Extracted: %s', path)
                    success = True
                except (IOError, os.error) as error:
                    error_message = 'OS error while creating file: %s (%s)' % (destination, error)
                except (zipfile.BadZipfile, rarfile.Error) as error:
                    error_message = 'Failed to extract file: %s in %s (%s)' % (path, archive_path, error)
                finally:
                    if source and not source.closed:
                        source.close()

                if not success:
                    log.error(error_message)
                    entry.fail(error_message)

                    if os.path.exists(destination):
                        log.debug('Cleaning up partially extracted file: %s', destination)
                    return
            else:
                log.verbose('File already exists: %s', destination)

        if config['delete_archive']:
            if hasattr(archive, 'volumelist'):
                volumes = archive.volumelist()
            else:
                volumes = [archive_path]

            archive.close()

            for volume in volumes:
                log.debug('Deleting volume: %s', volume)
                os.remove(volume)

            log.verbose('Deleted archive: %s', archive_file)
        else:
            archive.close()

    @plugin.priority(255)
    def on_task_output(self, task, config):
        """Task handler for archive_extract"""
        if isinstance(config, bool) and not config:
            return

        config = self.prepare_config(config)
        set_rar_tool(config)

        if rarfile:
            rarfile.PATH_SEP = os.path.sep

        for entry in task.accepted:
            self.handle_entry(entry, config)


@event('plugin.register')
def register_plugin():
    plugin.register(Decompress, 'decompress', api_ver=2)
    plugin.register(FilterArchives, 'archives', api_ver=2)
