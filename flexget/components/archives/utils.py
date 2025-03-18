"""Utilities for handling RAR and ZIP archives.

Provides wrapper archive and exception classes to simplify
archive extraction
"""

import os
import shutil
import zipfile
from pathlib import Path

from loguru import logger

try:
    import rarfile
except ImportError:
    rarfile = None

logger = logger.bind(name="archive")


class ArchiveError(Exception):
    """Base exception for archive."""


class NeedRarFile(ArchiveError):
    """Exception to be raised when rarfile module is missing."""


class BadArchive(ArchiveError):
    """Wrapper exception for BadZipFile and BadRarFile."""


class NeedFirstVolume(ArchiveError):
    """Wrapper exception for rarfile.NeedFirstVolume."""


class PathError(ArchiveError):
    """Exception to be raised when an archive file doesn't exist."""


class FSError(ArchiveError):
    """Exception to be raised on OS/IO exceptions."""


class FileAlreadyExists(ArchiveError):
    """Exception to be raised when destination file already exists."""


def rarfile_set_tool_path(config):
    """Manually set the path of unrar executable if it can't be resolved from the PATH environment variable."""
    unrar_tool = config["unrar_tool"]

    if unrar_tool:
        if not rarfile:
            logger.error("rar_tool specified with no rarfile module installed.")
        else:
            rarfile.UNRAR_TOOL = unrar_tool
            logger.debug("Set RarFile.unrar_tool to: {}", unrar_tool)


def rarfile_set_path_sep(separator):
    """Set the path separator on rarfile module."""
    if rarfile:
        rarfile.PATH_SEP = separator


def makepath(path: Path) -> None:
    """Make directories as needed."""
    if not Path(path).exists():
        logger.debug("Creating path: {}", path)
        Path(path).mkdir(parents=True)


class Archive:
    """Base archive class. Assumes an interface similar to zipfile.ZipFile or rarfile.RarFile."""

    def __init__(self, archive_object, path):
        self.path = path

        self.archive = archive_object(self.path)

    def close(self):
        """Release open resources."""
        self.archive.close()

    def delete(self):
        """Delete the volumes that make up this archive."""
        volumes = self.volumes()
        self.close()

        try:
            for volume in volumes:
                Path(volume).unlink()
                logger.verbose("Deleted archive: {}", volume)
        except OSError as error:
            raise FSError(error)

    def volumes(self):
        """Return the list of volumes that comprise this archive."""
        return [self.path]

    def infolist(self):
        """Return a list of info objects describing the contents of this archive."""
        infolist = []

        for info in self.archive.infolist():
            try:
                archive_info = ArchiveInfo(info)
                infolist.append(archive_info)
            except ValueError as e:
                logger.debug(e)

        return infolist

    def open(self, member):
        """Return file-like object from where the data of a member file can be read."""
        return self.archive.open(member)

    def extract_file(self, member, destination: Path):
        """Extract a member file to the specified destination."""
        try:
            with self.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
        except OSError as error:
            raise FSError(error)


class RarArchive(Archive):
    """Wrapper class for rarfile.RarFile."""

    def __init__(self, path):
        RarArchive.check_import()

        try:
            super().__init__(rarfile.RarFile, path)
        except rarfile.BadRarFile as error:
            raise BadArchive(error)
        except rarfile.NeedFirstVolume as error:
            raise NeedFirstVolume(error)
        except rarfile.Error as error:
            raise ArchiveError(error)

    def volumes(self):
        """Return the list of volumes that comprise this archive."""
        return self.archive.volumelist()

    def open(self, member):
        """Return file-like object from where the data of a member file can be read."""
        try:
            return super().open(member)
        except rarfile.Error as error:
            raise ArchiveError(error)

    @staticmethod
    def check_import():
        if not rarfile:
            raise NeedRarFile("Python module rarfile needed to handle RAR archives")


class ZipArchive(Archive):
    """Wrapper class for zipfile.ZipFile."""

    def __init__(self, path):
        try:
            super().__init__(zipfile.ZipFile, path)
        except zipfile.BadZipfile as error:
            raise BadArchive(error)

    def open(self, member):
        """Return file-like object from where the data of a member file can be read."""
        try:
            return super().open(member)
        except zipfile.BadZipfile as error:
            raise ArchiveError(error)


class ArchiveInfo:
    """Wrapper class for  archive info objects."""

    def __init__(self, info):
        self.info = info
        self.path = info.filename
        self.filename = os.path.basename(self.path)

        if self._is_dir():
            raise ValueError(f"Appears to be a directory: {self.path}")

    def _is_dir(self):
        """Indicate if info object looks to be a directory."""
        if hasattr(self.info, "isdir"):
            return self.info.isdir()
        return not self.filename

    def extract(self, archive, destination: Path):
        """Extract ArchiveInfo object to the specified destination."""
        dest_dir = destination.parent

        if destination.exists():
            raise FileAlreadyExists(f"File already exists: {destination}")

        logger.debug("Creating path: {}", dest_dir)
        makepath(dest_dir)

        try:
            archive.extract_file(self.info, destination)
            logger.verbose("Extracted: {} to {}", self.path, destination)
        except Exception:
            if destination.exists():
                logger.debug("Cleaning up partially extracted file: {}", destination)
                destination.unlink()

            raise


def open_archive(archive_path):
    """Return the appropriate archive object."""
    archive = None

    if not Path(archive_path).exists():
        raise PathError("Path doesn't exist")

    if zipfile.is_zipfile(archive_path):
        archive = ZipArchive(archive_path)
        logger.debug("Successfully opened ZIP: {}", archive_path)
    elif rarfile and rarfile.is_rarfile(archive_path):
        archive = RarArchive(archive_path)
        logger.debug("Successfully opened RAR: {}", archive_path)
    elif not rarfile:
        logger.warning("Rarfile module not installed; unable to handle RAR archives.")

    return archive


def is_archive(path):
    """Attempt to open an entry as an archive; return True on success, False on failure."""
    archive = None

    try:
        archive = open_archive(path)
        if archive:
            archive.close()
            return True
    except (OSError, ArchiveError) as error:
        logger.debug("Failed to open file as archive: {} ({})", path, error)

    return False
