import sys
import os
import logging

log = logging.getLogger('exists')

class FilterExists:

    """
        Reject entries that already exist in given path.

        Example:

        exists: /storage/movies/
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='filter', keyword='exists', callback=self.run)

    def run(self, feed):
        path = feed.config.get('exists', None)
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise Warning('Path %s does not exists' % path)
        # scan trough
        for root, dirs, files in os.walk(path):
            log.debug('Checking %s' % root)
            # convert filelists into utf-8 to avoid unicode problems
            dirs = [x.decode('utf-8', 'ignore') for x in dirs]
            files = [x.decode('utf-8', 'ignore') for x in files]
            for entry in feed.entries:
                if entry['title'] in dirs or entry['title'] in files:
                    log.debug('Found %s in %s' % (name, root))
                    feed.filter(entry)
                

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    from test_tools import MockFeed
    feed = MockFeed()
    feed.config['exists'] = sys.argv[1]
    e = {}
    e['url'] = 'http://127.0.0.1/test'
    e['title'] = sys.argv[2]
    feed.entries.append(e)
    
    fe = FilterExists()
    fe.run(feed)
    
