from __future__ import unicode_literals, division, absolute_import
import os
import logging
import platform

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
        for path in config:
            # unicode path causes crashes on some paths
            path = str(os.path.expanduser(path))
            if not os.path.exists(path):
                raise plugin.PluginWarning('Path %s does not exist' % path, log)
            # scan through
            for root, dirs, files in os.walk(path, followlinks=True):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                files = [x.decode('utf-8', 'ignore') for x in files]
                # windows file system is not case sensitive
                if platform.system() == 'Windows':
                    dirs = [s.lower() for s in dirs]
                    files = [s.lower() for s in files]
                for entry in task.accepted:
                    # priority is: filename, location (filename only), title
                    name = check = os.path.split(entry.get('filename', 
                        entry.get('location', entry['title'])))[1]
                    if platform.system() == 'Windows':
                        check = check.lower()
                    if check in dirs or check in files:
                        log.debug('Found %s in %s' % (name, root))
                        entry.reject(os.path.join(root, name))

@event('plugin.register')
def register_plugin():
    plugin.register(FilterExists, 'exists', api_ver=2)
