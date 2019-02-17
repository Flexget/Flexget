"""
Utilities for handling RAR and ZIP archives

Provides wrapper archive and exception classes to simplify
archive extraction
"""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import zipfile
import os
import shutil
import logging

try:
    import rarfile
except ImportError:
    rarfile = None

log = logging.getLogger('archive')


class ArchiveError(Exception):
    """Base exception for archive"""

    pass


class NeedRarFile(ArchiveError):
    """Exception to be raised when rarfile module is missing"""

    pass


class BadArchive(ArchiveError):
    """Wrapper exception for BadZipFile and BadRarFile"""

    pass


class NeedFirstVolume(ArchiveError):
    """Wrapper exception for rarfile.NeedFirstVolume"""

    pass


class PathError(ArchiveError):
    """Exception to be raised when an archive file doesn't exist"""

    pass


class FSError(ArchiveError):
    """Exception to be raised on OS/IO exceptions"""

    pass


class FileAlreadyExists(ArchiveError):
    """Exception to be raised when destination file already exists"""

    pass


def rarfile_set_tool_path(config):
    """
    Manually set the path of unrar executable if it can't be resolved from the
    PATH environment variable
    """
    unrar_tool = config['unrar_tool']

    if unrar_tool:
        if not rarfile:
            log.error('rar_tool specified with no rarfile module installed.')
        else:
            rarfile.UNRAR_TOOL = unrar_tool
            log.debug('Set RarFile.unrar_tool to: %s', unrar_tool)


def rarfile_set_path_sep(separator):
    """
    Set the path separator on rarfile module
    """
    if rarfile:
        rarfile.PATH_SEP = separator


def makepath(path):
    """Make directories as needed"""
    if not os.path.exists(path):
        log.debug('Creating path: %s', path)
        os.makedirs(path)


class Archive(object):
    """
    Base archive class. Assumes an interface similar to
    zipfile.ZipFile or rarfile.RarFile
    """

    def __init__(self, archive_object, path):
        self.path = path

        self.archive = archive_object(self.path)

    def close(self):
        """Release open resources."""
        self.archive.close()

    def delete(self):
        """Delete the volumes that make up this archive"""
        volumes = self.volumes()
        self.close()

        try:
            for volume in volumes:
                os.remove(volume)
                log.verbose('Deleted archive: %s', volume)
        except (IOError, os.error) as error:
            raise FSError(error)

    def volumes(self):
        """Returns the list of volumes that comprise this archive"""
        return [self.path]

    def infolist(self):
        """Returns a list of info objects describing the contents of this archive"""
        infolist = []

        for info in self.archive.infolist():
            try:
                archive_info = ArchiveInfo(info)
                infolist.append(archive_info)
            except ValueError as e:
                log.debug(e)

        return infolist

    def open(self, member):
        """Returns file-like object from where the data of a member file can be read."""
        return self.archive.open(member)

    def extract_file(self, member, destination):
        """Extract a member file to the specified destination"""
        try:
            with self.open(member) as source:
                with open(destination, 'wb') as target:
                    shutil.copyfileobj(source, target)
        except (IOError, os.error) as error:
            raise FSError(error)

        log.verbose('Extracted: %s', member)


class RarArchive(Archive):
    """
    Wrapper class for rarfile.RarFile
    """

    def __init__(self, path):
        if not rarfile:
            raise NeedRarFile('Python module rarfile needed to handle RAR archives')

        try:
            super(RarArchive, self).__init__(rarfile.RarFile, path)
        except rarfile.BadRarFile as error:
            raise BadArchive(error)
        except rarfile.NeedFirstVolume as error:
            raise NeedFirstVolume(error)
        except rarfile.Error as error:
            raise ArchiveError(error)

    def volumes(self):
        """Returns the list of volumes that comprise this archive"""
        return self.archive.volumelist()

    def open(self, member):
        """Returns file-like object from where the data of a member file can be read."""
        try:
            return super(RarArchive, self).open(member)
        except rarfile.Error as error:
            raise ArchiveError(error)


class ZipArchive(Archive):
    """
    Wrapper class for zipfile.ZipFile
    """

    def __init__(self, path):
        try:
            super(ZipArchive, self).__init__(zipfile.ZipFile, path)
        except zipfile.BadZipfile as error:
            raise BadArchive(error)

    def open(self, member):
        """Returns file-like object from where the data of a member file can be read."""
        try:
            return super(ZipArchive, self).open(member)
        except zipfile.BadZipfile as error:
            raise ArchiveError(error)


class ArchiveInfo(object):
    """Wrapper class for  archive info objects"""

    def __init__(self, info):
        self.info = info
        self.path = info.filename
        self.filename = os.path.basename(self.path)

        if self._is_dir():
            raise ValueError('Appears to be a directory: %s' % self.path)

    def _is_dir(self):
        """Indicates if info object looks to be a directory"""

        if hasattr(self.info, 'isdir'):
            return self.info.isdir()
        else:
            return not self.filename

    def extract(self, archive, destination):
        """Extract ArchiveInfo object to the specified destination"""
        dest_dir = os.path.dirname(destination)

        if os.path.exists(destination):
            raise FileAlreadyExists('File already exists: %s' % destination)

        log.debug('Creating path: %s', dest_dir)
        makepath(dest_dir)

        try:
            archive.extract_file(self.info, destination)
        except Exception as error:
            if os.path.exists(destination):
                log.debug('Cleaning up partially extracted file: %s', destination)
                os.remove(destination)

            raise error


def open_archive(archive_path):
    """
    Returns the appropriate archive object
    """

    archive = None

    if not os.path.exists(archive_path):
        raise PathError('Path doesn\'t exist')

    if zipfile.is_zipfile(archive_path):
        archive = ZipArchive(archive_path)
        log.debug('Successfully opened ZIP: %s', archive_path)
    elif rarfile and rarfile.is_rarfile(archive_path):
        archive = RarArchive(archive_path)
        log.debug('Successfully opened RAR: %s', archive_path)
    else:
        if not rarfile:
            log.warning('Rarfile module not installed; unable to handle RAR archives.')

    return archive


def is_archive(path):
    """
    Attempts to open an entry as an archive; returns True on success, False on failure.
    """

    archive = None

    try:
        archive = open_archive(path)
        if archive:
            archive.close()
            return True
    except (IOError, ArchiveError) as error:
        log.debug('Failed to open file as archive: %s (%s)', path, error)

    return False
