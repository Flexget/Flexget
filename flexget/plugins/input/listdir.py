"""Plugin for filesystem tasks."""
from __future__ import unicode_literals, division, absolute_import
import os
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('listdir')


class Listdir(object):
    """
    Uses local path content as an input.

    Example::

      listdir: /storage/movies/
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('path')
        bundle = root.accept('list')
        bundle.accept('path')
        return root

    def on_task_input(self, task, config):
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        entries = []
        for path in config:
            path = os.path.expanduser(path)
            for name in os.listdir(unicode(path)):
                e = Entry()
                filepath = os.path.join(path, name)
                if os.path.isfile(filepath):
                    e['title'] = os.path.splitext(name)[0]
                else:
                    e['title'] = name
                e['location'] = filepath
                # Windows paths need an extra / preceded to them
                if not filepath.startswith('/'):
                    filepath = '/' + filepath
                e['url'] = 'file://%s' % filepath
                e['filename'] = name
                entries.append(e)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Listdir, 'listdir', api_ver=2)
