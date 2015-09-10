from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import re
import sys

from path import Path

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('find')


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

    def on_task_input(self, task, config):
        self.prepare_config(config)
        entries = []
        match = re.compile(config['regexp'], re.IGNORECASE).match
        for folder in config['path']:
            folder = Path(folder).expanduser()
            log.debug('scanning %s' % folder)
            if config['recursive']:
                files = folder.walk(errors='ignore')
            else:
                files = folder.listdir()
            for item in files:
                e = Entry()
                try:
                    # TODO: config for listing files/dirs/both
                    if item.isdir():
                        continue
                except UnicodeError as e:
                    log.warning('Filename `%s` in `%s` is not decodable by declared filesystem encoding `%s`. '
                                'Either your environment does not declare the correct encoding, or this filename '
                                'is incorrectly encoded.' %
                                (item.name, item.dirname(), sys.getfilesystemencoding()))
                    continue

                e['title'] = item.namebase
                # If mask fails continue
                if not match(item.name):
                    continue
                try:
                    e['timestamp'] = datetime.fromtimestamp(item.getmtime())
                except ValueError as e:
                    log.debug('Error setting timestamp for %s: %s' % (item, e))
                e['location'] = item
                # Windows paths need an extra / prepended to them for url
                if not item.startswith('/'):
                    item = '/' + item
                e['url'] = 'file://%s' % item
                entries.append(e)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputFind, 'find', api_ver=2)
