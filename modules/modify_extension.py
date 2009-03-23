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
        manager.register('extension')

    def validator(self):
        import validator
        root = validator.factory()
        root.accept('text')
        root.accept('number')
        return root

    def feed_modify(self, feed):
        ext = feed.config.get('extension')
        if ext.startswith('.'):
            ext = ext[1:]
        for entry in feed.entries:
            entry['filename'] = '%s.%s' % (entry.get('filename', entry['title']), ext)
            log.debug('setting filename %s' % entry['filename'])
