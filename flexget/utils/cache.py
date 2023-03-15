import hashlib
import os
from typing import Tuple

import requests
from loguru import logger

logger = logger.bind(name='utils.cache')


# TODO refactor this to use lru_cache
def cached_resource(
    url: str,
    base_dir: str,
    force: bool = False,
    max_size: int = 250,
    directory: str = 'cached_resources',
) -> Tuple[str, str]:
    """
    Caches a remote resource to local filesystem. Return a tuple of local file name and mime type, use primarily
    for API/WebUI.

    :param url: Resource URL
    :param force: Does not check for existence of cached resource, fetches the remote URL, ignores directory size limit
    :param max_size: Maximum allowed size of directory, in MB.
    :param directory: Name of directory to use. Default is `cached_resources`
    :return: Tuple of file path and mime type
    """
    mime_type = None
    hashed_name = hashlib.md5(url.encode('utf-8')).hexdigest()
    file_path = os.path.join(base_dir, directory, hashed_name)
    directory = os.path.dirname(file_path)

    if not os.path.exists(file_path) or force:
        logger.debug(f'caching {url}')
        response = requests.get(url)
        response.raise_for_status()
        mime_type = response.headers.get('content-type')
        content = response.content
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Checks directory size and trims if necessary.
        size = dir_size(directory) / (1024 * 1024.0)
        if not force:
            while size >= max_size:
                logger.debug(
                    f'directory {size} size is over the allowed limit of {max_size}, trimming'
                )
                trim_dir(directory)
                size = dir_size(directory) / (1024 * 1024.0)

        with open(file_path, 'wb') as file:
            file.write(content)
    return file_path, mime_type


def dir_size(directory: str) -> int:
    """
    Sums the size of all files in a given dir. Not recursive.

    :param directory: Directory to check
    :return: Summed size of all files in Bytes.
    """
    size = 0
    for file in os.listdir(directory):
        filename = os.path.join(directory, file)
        size += os.path.getsize(filename)
    return size


def trim_dir(directory: str) -> None:
    """
    Removed the least accessed file on a given dir

    :param directory: Directory to check
    """

    def access_time(f: str) -> float:
        return os.stat(os.path.join(directory, f)).st_atime

    files = sorted(os.listdir(directory), key=access_time)
    file_name = os.path.join(directory, files[0])
    logger.debug('removing least accessed file: {}', file_name)
    os.remove(file_name)
