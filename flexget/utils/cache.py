import hashlib
from pathlib import Path

import requests

from flexget.utils.tools import log


def cached_resource(url, base_dir, force=False, max_size=250, directory='cached_resources'):
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
    file_path = Path(base_dir) / directory / hashed_name
    directory = file_path.parent

    if not file_path.exists() or force:
        log.debug('caching %s', url)
        response = requests.get(url)
        response.raise_for_status()
        mime_type = response.headers.get('content-type')
        content = response.content
        directory.mkdir(parents=True, exist_ok=True)

        # Checks directory size and trims if necessary.
        size = dir_size(directory) / (1_024 * 1_024.0)
        if not force:
            while size >= max_size:
                log.debug('directory %s size is over the allowed limit of %s, trimming', size, max_size)
                trim_dir(directory)
                size = dir_size(directory) / (1_024 * 1_024.0)
        file_path.write_bytes(content)

    return str(file_path), mime_type


def dir_size(directory: Path):
    """
    Sums the size of all files in a given dir. Not recursive.

    :param directory: Directory to check
    :return: Summed size of all files in Bytes.
    """
    return sum(file.stat().st_size for file in directory.iterdir())


def trim_dir(directory: Path):
    """
    Removed the least accessed file on a given dir

    :param directory: Directory to check
    """

    def access_time(file: Path):
        return file.stat().st_atime

    files = sorted(directory.iterdir(), key=access_time)
    file_name = directory / files[0]
    log.debug('removing least accessed file: %s', file_name)
    file_name.unlink()
