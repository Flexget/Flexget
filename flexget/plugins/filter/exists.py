from __future__ import unicode_literals, division, absolute_import
import os
import logging

from flexget.config_schema import one_or_more
from flexget.plugin import register_plugin, priority, PluginWarning

log = logging.getLogger('exists')


class FilterExists(object):

    """
        Reject entries that already exist in given path.

        Example::

          exists: /storage/movies/
    """

    schema = one_or_more({'type': 'string', 'format': 'path'})

    def get_config(self, task):
        config = task.config.get('exists', None)
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    @priority(-1)
    def on_task_filter(self, task):
        if not task.accepted:
            log.debug('No accepted entries, not scanning for existing.')
            return
        log.verbose('Scanning path(s) for existing files.')
        config = self.get_config(task)
        for path in config:
            # unicode path causes crashes on some paths
            path = str(os.path.expanduser(path))
            if not os.path.exists(path):
                raise PluginWarning('Path %s does not exist' % path, log)
            # scan through
            for root, dirs, files in os.walk(path, followlinks=True):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                files = [x.decode('utf-8', 'ignore') for x in files]
                for entry in task.accepted:
                    name = entry['title']
                    if name in dirs or name in files:
                        log.debug('Found %s in %s' % (name, root))
                        entry.reject(os.path.join(root, name))

register_plugin(FilterExists, 'exists')
