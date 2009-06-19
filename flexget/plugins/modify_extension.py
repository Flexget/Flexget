import logging
from flexget.plugin import *

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('extension')

class ModifyExtension:

    """
        Allows specifying file extension explicitly when all other built-in detection mechanisms fail.
    
        Example:

        extension: nzb
    """
    def validator(self):
        from flexget import validator
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

register_plugin(ModifyExtension, 'extension')
