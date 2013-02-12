from __future__ import unicode_literals, division, absolute_import
import ntpath
import sys
import re

os_mode = None  # Can be 'windows', 'mac', 'linux' or None. None will auto-detect os.
replace_maps = {
    'windows': {
        '[:*?"<>| ]+': ' ',  # Turn illegal characters into a space
        r'\.\s*([/\\]|$)': r'\1'},  # Dots cannot end file or directory names
    'mac': {
        '[: ]+': ' '},
    'linux': {}}  # No replacements on linux


def pathscrub(dirty_path, os=None, filename=False):
    """
    Strips illegal characters for a given os from a path.

    :param dirty_path: Path to be scrubbed.
    :param os: Defines which os mode should be used, can be 'windows', 'mac', 'linux', or None to auto-detect
    :param filename: If this is True, path separators will be replaced with '-'
    :return: A valid path.
    """

    # See if global os_mode has been defined by pathscrub plugin
    if os_mode and not os:
        os = os_mode

    if os:
        # If os is defined, use replacements for that os
        replace_map = replace_maps[os_mode]
    else:
        # If os is not defined, try to detect appropriate
        drive, path = ntpath.splitdrive(dirty_path)
        if sys.platform.startswith('win') or drive:
            replace_map = replace_maps['windows']
        elif sys.platform.startswith('darwin'):
            replace_map = replace_maps['mac']
        else:
            replace_map = replace_maps['linux']

    # Make sure not to mess with windows drive specifications
    drive, path = ntpath.splitdrive(dirty_path)
    for search, replace in replace_map.iteritems():
        path = re.sub(search, replace, path)

    if filename:
        path = path.replace('/', '-').replace('\\', '-')

    return drive + path.strip()
