import logging
import pipes
import shlex
import subprocess
from flexget.plugin import *

log = logging.getLogger('exec')


class OutputExec:
    """
    Execute command for entries that reach output.

    Example:

    exec: echo 'found %(title)s at %(url)s > file

    You can use all (available) entry fields in the command.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('text')

    def on_feed_output(self, feed):
        for entry in feed.accepted:
            try:
                cmd = feed.config['exec']
                args = []
                # shlex is documented to not work on unicode
                for arg in shlex.split(cmd.encode('utf-8'), comments=True):
                    arg = unicode(arg, 'utf-8')
                    formatted = arg % entry
                    if formatted != arg:
                        arg = pipes.quote(formatted)
                    args.append(arg)
                cmd = ' '.join(args)
            except KeyError, e:
                log.error('Entry %s does not have required field %s' % (entry['title'], e.message))
                continue
            if feed.manager.options.test:
                log.info('Would execute: %s' % cmd)
                continue
            log.debug('executing cmd: %s' % cmd)
            p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=False)
            (r, w) = (p.stdout, p.stdin)
            response = r.read()
            r.close()
            w.close()
            if response:
                log.info('Stdout: %s' % response)

register_plugin(OutputExec, 'exec')
