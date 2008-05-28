import yaml
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
        manager.register(event='output', keyword='exec', callback=self.run)

    def run(self, feed):
        for entry in feed.entries:
            cmd = feed.config['exec'] % entry
            log.debug('executing cmd: %s' % cmd)
            (stdin, stdout, stderr) = os.popen4(cmd)
            stdin.close()
            stdout.close()
            stderr.close()
