from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, register_parser_option

log = logging.getLogger('try_regexp')


class PluginTryRegexp:
    """
        This plugin allows user to test regexps for a task.
    """

    def __init__(self):
        self.abort = False

    def matches(self, entry, regexp):
        """Return True if any of the entry string fields match given regexp"""
        import re
        for field, value in entry.iteritems():
            if not isinstance(value, basestring):
                continue
            if re.search(regexp, value, re.IGNORECASE | re.UNICODE):
                return (True, field)
        return (False, None)

    def on_task_filter(self, task):
        if not task.manager.options.try_regexp:
            return
        if self.abort:
            return

        print '-' * 79
        print 'Hi there, welcome to try regexps in realtime!'
        print 'Press ^D or type \'exit\' to continue. Type \'continue\' to continue non-interactive execution.'
        print 'Task \'%s\' has %s entries, enter regexp to see what matches it.' % (task.name, len(task.entries))
        while (True):
            try:
                s = raw_input('--> ')
                if s == 'exit':
                    break
                if s == 'abort' or s == 'continue':
                    self.abort = True
                    break
            except EOFError:
                break

            count = 0
            for entry in task.entries:
                try:
                    match, field = self.matches(entry, s)
                    if match:
                        print 'Title: %-40s URL: %-30s From: %s' % (entry['title'], entry['url'], field)
                        count += 1
                except:
                    print 'Invalid regular expression'
                    break
            print '%s of %s entries matched' % (count, len(task.entries))
        print 'Bye!'

register_plugin(PluginTryRegexp, '--try-regexp', builtin=True)
register_parser_option('--try-regexp', action='store_true', dest='try_regexp', default=False,
                       help='Try regular expressions interactively.')
