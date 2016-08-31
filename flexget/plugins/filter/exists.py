from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
import platform

from path import Path

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

log = logging.getLogger('exists')


class FilterExists(object):
    """
        Reject entries that already exist in given path.

        Example::

          exists: /storage/movies/
    """

    schema = one_or_more({'type': 'string', 'format': 'path'})

    def prepare_config(self, config):
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            log.debug('No accepted entries, not scanning for existing.')
            return
        log.verbose('Scanning path(s) for existing files.')
        config = self.prepare_config(config)
        filenames = {}
        for folder in config:
            folder = Path(folder).expanduser()
            if not folder.exists():
                raise plugin.PluginWarning('Path %s does not exist' % folder, log)
            for p in folder.walk(errors='ignore'):
                key = p.name
                # windows file system is not case sensitive
                if platform.system() == 'Windows':
                    key = key.lower()
                filenames[key] = p
        for entry in task.accepted:
            # priority is: filename, location (filename only), title
            name = Path(entry.get('filename', entry.get('location', entry['title']))).name
            if platform.system() == 'Windows':
                name = name.lower()
            if name in filenames:
                log.debug('Found %s in %s' % (name, filenames[name]))
                entry.reject('exists in %s' % filenames[name])


@event('plugin.register')
def register_plugin():
    plugin.register(FilterExists, 'exists', api_ver=2)
