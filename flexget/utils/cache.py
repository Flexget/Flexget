from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

import requests
from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path

logger = logger.bind(name='utils.cache')


# TODO: refactor this to use lru_cache
def cached_resource(
    url: str,
    base_dir: Path,
    force: bool = False,
    max_size: int = 250,
    directory: str = 'cached_resources',
) -> tuple[Path, str]:
    """Cache a remote resource to local filesystem.

    Return a tuple of local file name and mime type, use primarily for API/WebUI.

    :param url: Resource URL
    :param force: Does not check for existence of cached resource, fetches the remote URL, ignores directory size limit
    :param max_size: Maximum allowed size of directory, in MB.
    :param directory: Name of directory to use. Default is `cached_resources`
    :return: Tuple of file path and mime type
    """
    mime_type = None
    hashed_name = hashlib.md5(url.encode('utf-8')).hexdigest()
    file_path = base_dir / directory / hashed_name
    directory = file_path.parent

    if not file_path.exists() or force:
        logger.debug('caching {}', url)
        response = requests.get(url)
        response.raise_for_status()
        mime_type = response.headers.get('content-type')
        content = response.content
        if not directory.exists():
            directory.mkdir(parents=True)

        # Checks directory size and trims if necessary.
        size = dir_size(directory) / (1024 * 1024.0)
        if not force:
            while size >= max_size:
                logger.debug(
                    'directory {} size is over the allowed limit of {}, trimming', size, max_size
                )
                trim_dir(directory)
                size = dir_size(directory) / (1024 * 1024.0)

        with file_path.open('wb') as file:
            file.write(content)
    return file_path, mime_type


def dir_size(directory: Path) -> int:
    """Sum the size of all files in a given dir. Not recursive.

    :param directory: Directory to check
    :return: Summed size of all files in Bytes.
    """
    size = 0
    for file in os.listdir(directory):
        filename = directory / file
        size += filename.stat().st_size
    return size


def trim_dir(directory: Path) -> None:
    """Remove the least accessed file on a given dir.

    :param directory: Directory to check
    """

    def access_time(f: str) -> float:
        return (directory / f).stat().st_atime

    files = sorted(os.listdir(directory), key=access_time)
    file_name = directory / files[0]
    logger.debug('removing least accessed file: {}', file_name)
    file_name.unlink()
