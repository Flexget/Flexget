from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console

log = logging.getLogger('try_regexp')


class PluginTryRegexp(object):
    """
        This plugin allows user to test regexps for a task.
    """

    def __init__(self):
        self.abort = False

    def matches(self, entry, regexp):
        """Return True if any of the entry string fields match given regexp"""
        import re
        for field, value in entry.items():
            if not isinstance(value, basestring):
                continue
            if re.search(regexp, value, re.IGNORECASE | re.UNICODE):
                return (True, field)
        return (False, None)

    def on_task_filter(self, task, config):
        if not task.options.try_regexp:
            return
        if self.abort:
            return

        console('-' * 79)
        console('Hi there, welcome to try regexps in realtime!')
        console('Press ^D or type \'exit\' to continue. Type \'continue\' to continue non-interactive execution.')
        console('Task \'%s\' has %s entries, enter regexp to see what matches it.' % (task.name, len(task.entries)))
        while (True):
            try:
                s = input('--> ')
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
                        console('Title: %-40s URL: %-30s From: %s' % (entry['title'], entry['url'], field))
                        count += 1
                except:
                    console('Invalid regular expression')
                    break
            console('%s of %s entries matched' % (count, len(task.entries)))
        console('Bye!')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTryRegexp, '--try-regexp', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--try-regexp', action='store_true', dest='try_regexp', default=False,
                                               help='try regular expressions interactively')
