import os
import logging
from flexget.plugin import *

log = logging.getLogger('exists')

class FilterExists:

    """
        Reject entries that already exist in given path.

        Example:

        exists: /storage/movies/
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('path')
        bundle = root.accept('list')
        bundle.accept('path')
        return root
        
    def get_config(self, feed):
        config = feed.config.get('exists', None)
        #if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    def on_feed_filter(self, feed):
        config = self.get_config(feed)
        for path in config:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                raise PluginWarning('Path %s does not exist' % path, log)
            # scan through
            for root, dirs, files in os.walk(path):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                files = [x.decode('utf-8', 'ignore') for x in files]
                for entry in feed.entries:
                    name = entry['title']
                    if name in dirs or name in files:
                        log.debug('Found %s in %s' % (name, root))
                        feed.reject(entry, '%s/%s' % (name, root))

register_plugin(FilterExists, 'exists', priorities={'filter': -1})
