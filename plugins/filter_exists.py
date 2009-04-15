import os
import logging
from manager import PluginWarning

log = logging.getLogger('exists')

class FilterExists:

    """
        Reject entries that already exist in given path.

        Example:

        exists: /storage/movies/
    """

    def register(self, manager, parser):
        manager.register('exists')

    def validator(self):
        import validator
        return validator.factory('text') # TODO: path

    def feed_filter(self, feed):
        path = feed.config.get('exists', None)
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise PluginWarning('Path %s does not exists' % path, log)
        # scan trough
        for root, dirs, files in os.walk(path):
            # convert filelists into utf-8 to avoid unicode problems
            dirs = [x.decode('utf-8', 'ignore') for x in dirs]
            files = [x.decode('utf-8', 'ignore') for x in files]
            for entry in feed.entries:
                name = entry['title']
                if name in dirs or name in files:
                    log.debug('Found %s in %s' % (name, root))
                    feed.reject(entry, '%s/%s' % (name, root))
