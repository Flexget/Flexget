from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import os
import re
import sys

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.cached_input import cached

log = logging.getLogger('find')
# Default to utf-8 if we get None from getfilesystemencoding()
FS_ENCODING = sys.getfilesystemencoding() or 'utf-8'


def fsencode(filename):
    """
    Prepares a filename for use with system calls.

    On Windows, keeps paths as native strings.
    On unixy systems encodes to a bytestring using the filesystem encoding.
    """
    if isinstance(filename, unicode):
        if sys.platform.startswith('win'):
            return filename
        else:
            # Linuxy systems can have trouble unless we give them a bytestring path
            return filename.encode(FS_ENCODING)
    elif isinstance(filename, str):
        return filename
    else:
        raise TypeError('expected bytes or str, not %s' % type(filename).__name__)


def fsdecode(filename, replace=False):
    """
    Makes sure a filename returned from a system call is converted back to a native string.

    :param bool replace: If replace is set to True, this function will mangle the path rather than throw an error.
        This can be useful for debug output, but not for accessing the file system any longer.
    """
    if isinstance(filename, str):
        return filename.decode(FS_ENCODING, 'replace' if replace else 'strict')
    elif isinstance(filename, unicode):
        return filename
    else:
        raise TypeError('expected bytes or str, not %s' % type(filename).__name__)


class InputFind(object):
    """
    Uses local path content as an input, recurses through directories and creates entries for files that match mask.

    You can specify either the mask key, in shell file matching format, (see python fnmatch module,) or regexp key.

    Example::

      find:
        path: /storage/movies/
        mask: *.avi

    Example::

      find:
        path:
          - /storage/movies/
          - /storage/tv/
        regexp: .*\.(avi|mkv)$
    """

    schema = {
        'type': 'object',
        'properties': {
            'path': one_or_more({'type': 'string', 'format': 'path'}),
            'mask': {'type': 'string'},
            'regexp': {'type': 'string', 'format': 'regex'},
            'recursive': {'type': 'boolean'}
        },
        'required': ['path'],
        'additionalProperties': False
    }

    def prepare_config(self, config):
        from fnmatch import translate
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], basestring):
            config['path'] = [config['path']]
        config.setdefault('recursive', False)
        # If mask was specified, turn it in to a regexp
        if config.get('mask'):
            config['regexp'] = translate(config['mask'])
        # If no mask or regexp specified, accept all files
        if not config.get('regexp'):
            config['regexp'] = '.'

    @cached('find')
    def on_task_input(self, task, config):
        self.prepare_config(config)
        entries = []
        match = re.compile(config['regexp'], re.IGNORECASE).match
        for path in config['path']:
            log.debug('scanning %s' % path)
            # unicode causes problems in here on linux (#989)
            fs_path = fsencode(path)
            fs_path = os.path.expanduser(fs_path)
            for fs_item in os.walk(fs_path):
                # Make sure subfolder is decodable
                try:
                    fsdecode(fs_item[0])
                except UnicodeDecodeError as e:
                    log.warning('Directory `%s` in `%s` encoding broken? %s' %
                                (fsdecode(fs_item[0], replace=True), fsdecode(fs_path, replace=True), e))
                    continue
                for fs_name in fs_item[2]:
                    e = Entry()
                    # Make sure filename is decodable
                    try:
                        fsdecode(fs_name)
                    except UnicodeDecodeError as e:
                        log.warning('Filename `%s` in `%s` is not decodable by declared filesystem encoding `%s`. '
                                    'Either your environment does not declare the correct encoding, or this filename '
                                    'is incorrectly encoded.' %
                                    (fsdecode(fs_name, replace=True), fsdecode(fs_item[0], replace=True), FS_ENCODING))
                        continue

                    e['title'] = fsdecode(os.path.splitext(fs_name)[0])
                    # If mask fails continue
                    if not match(fsdecode(fs_name)):
                        continue
                    fs_filepath = os.path.join(fs_item[0], fs_name)
                    try:
                        e['timestamp'] = datetime.fromtimestamp(os.path.getmtime(fs_filepath))
                    except ValueError as e:
                        log.debug('Error setting timestamp for %s: %s' % (fsdecode(fs_filepath), e))
                    # We are done calling os.path functions, turn filepath back into a native string
                    filepath = fsdecode(fs_filepath)
                    e['location'] = filepath
                    # Windows paths need an extra / prepended to them for url
                    if not filepath.startswith('/'):
                        filepath = '/' + filepath
                    e['url'] = 'file://%s' % filepath
                    entries.append(e)
                # If we are not searching recursively, break after first (base) directory
                if not config['recursive']:
                    break
        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(InputFind, 'find', api_ver=2)
