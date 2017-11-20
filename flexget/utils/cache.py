from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import hashlib
import io
import os

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
    file_path = os.path.join(base_dir, directory, hashed_name)
    directory = os.path.dirname(file_path)

    if not os.path.exists(file_path) or force:
        log.debug('caching %s', url)
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
                log.debug('directory %s size is over the allowed limit of %s, trimming', size, max_size)
                trim_dir(directory)
                size = dir_size(directory) / (1024 * 1024.0)

        with io.open(file_path, 'wb') as file:
            file.write(content)
    return file_path, mime_type


def dir_size(directory):
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


def trim_dir(directory):
    """
    Removed the least accessed file on a given dir

    :param directory: Directory to check
    """

    def access_time(f):
        return os.stat(os.path.join(directory, f)).st_atime

    files = sorted(os.listdir(directory), key=access_time)
    file_name = os.path.join(directory, files[0])
    log.debug('removing least accessed file: %s', file_name)
    os.remove(file_name)
