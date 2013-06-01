from __future__ import unicode_literals, division, absolute_import
import logging
import os
import re
import sys

from flexget.entry import Entry
from flexget.plugin import register_plugin
from flexget.utils.cached_input import cached

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

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('path', key='path', required=True)
        root.accept('list', key='path').accept('path')
        root.accept('text', key='mask')
        root.accept('regexp', key='regexp')
        root.accept('boolean', key='recursive')
        return root

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
        # Default to utf-8 if we get None from getfilesystemencoding()
        fs_encoding = sys.getfilesystemencoding() or 'utf-8'
        for path in config['path']:
            log.debug('scanning %s' % path)
            # unicode causes problems in here (#989)
            path = path.encode(fs_encoding)
            path = os.path.expanduser(path)
            for item in os.walk(path):
                log.debug('item: %s' % str(item))
                for name in item[2]:
                    # If mask fails continue
                    if match(name) is None:
                        continue
                    e = Entry()
                    try:
                        # Convert back to unicode
                        e['title'] = os.path.splitext(name.decode(fs_encoding))[0]
                    except UnicodeDecodeError:
                        log.warning('Filename `%r` in `%s` encoding broken?' %
                                    (name.decode('utf-8', 'replace'), item[0]))
                        continue
                    filepath = os.path.join(item[0], name).decode(fs_encoding)
                    e['location'] = filepath
                    # Windows paths need an extra / prepended to them for url
                    if not filepath.startswith('/'):
                        filepath = '/' + filepath
                    e['url'] = 'file://%s' % (filepath)
                    entries.append(e)
                # If we are not searching recursively, break after first (base) directory
                if not config['recursive']:
                    break
        return entries

register_plugin(InputFind, 'find', api_ver=2)
