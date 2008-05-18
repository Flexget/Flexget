import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('extension')

class ModifyExtension:

    """
        Allows specifying file extension explicitly when all other built-in detection mechanisms fail.
    
        Example:

        extension: nzb
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='modify', keyword='extension', callback=self.run)

    def run(self, feed):
        ext = feed.config.get('extension')
        if not ext.startswith('.'):
            ext = '.%s' % ext
        for entry in feed.entries:
            if not entry.has_key('filename'):
                entry['filename'] = '%s%s' % (entry['title'], ext)
                log.debug('generated filename %s' % entry['filename'])

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    from test_tools import MockFeed

    feed = MockFeed()
    feed.config['extension'] = sys.argv[1]

    e = {}
    e['title'] = 'mock title'
    e['url'] = 'http://127.0.0.1/'
    feed.entries.append(e)

    module = ModifyExtension()
    module.run(feed)

    feed.dump_entries()
