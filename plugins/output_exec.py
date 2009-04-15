import os
import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('exec')

class OutputExec:

    """
    Execute command for entries that reach output.
    
    Example:
    
    exec: echo 'found %(title)s at %(url)s > file
    
    You can use all (available) entry fields in the command.
    """

    def register(self, manager, parser):
        manager.register('exec')

    def validator(self):
        import validator
        return validator.factory('text')

    def feed_output(self, feed):
        for entry in feed.accepted:
            cmd = feed.config['exec'] % entry
            log.debug('executing cmd: %s' % cmd)
            (r, w) = os.popen4(cmd)
            r.close()
            w.close()
