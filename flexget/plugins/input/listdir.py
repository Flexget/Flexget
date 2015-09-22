"""Plugin for filesystem tasks."""
from __future__ import unicode_literals, division, absolute_import
import os
import logging

from path import Path

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more

log = logging.getLogger('listdir')


class Listdir(object):
    """
    Uses local path content as an input.

    Example::

      listdir: /storage/movies/
    """

    schema = one_or_more({'type': 'string', 'format': 'path'})

    def on_task_input(self, task, config):
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        entries = []
        for folder in config:
            folder = Path(folder).expanduser()
            try:
                dir_files = folder.listdir()
            except OSError as e:
                log.error('Path %s could not be accessed: %s' % (folder, e.strerror))
                continue
            for filepath in dir_files:
                try:
                    filepath.exists()
                except UnicodeError:
                    log.error('file %s not decodable with filesystem encoding' % filepath)
                    continue
                e = Entry()
                if filepath.isfile():
                    e['title'] = filepath.namebase
                else:
                    e['title'] = filepath.name
                e['location'] = filepath
                # Windows paths need an extra / preceded to them
                if not filepath.startswith('/'):
                    filepath = '/' + filepath
                e['url'] = 'file://%s' % filepath
                e['filename'] = filepath.name
                entries.append(e)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Listdir, 'listdir', api_ver=2)
