import os
import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('exists')

class FilterExists:

    """
        Reject entries that already exist in given path.

        Example:

        exists: /storage/movies/
    """

    def register(self, manager, parser):
        manager.register(event='filter', keyword='exists', callback=self.run)

    def run(self, feed):
        path = feed.config.get('exists', None)
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise Warning('Path %s does not exists' % path)
        # scan trough
        for root, dirs, files in os.walk(path):
            # convert filelists into utf-8 to avoid unicode problems
            dirs = [x.decode('utf-8', 'ignore') for x in dirs]
            files = [x.decode('utf-8', 'ignore') for x in files]
            for entry in feed.entries:
                name = entry['title']
                if name in dirs or name in files:
                    log.debug('Found %s in %s' % (name, root))
                    feed.filter(entry)
