import re

from loguru import logger

from flexget import options, plugin
from flexget.event import event
from flexget.terminal import console

logger = logger.bind(name='try_regexp')


class PluginTryRegexp:
    """
        This plugin allows user to test regexps for a task.
    """

    def __init__(self):
        self.abort = False

    def matches(self, entry, regexp):
        """Return True if any of the entry string fields match given regexp"""
        for field, value in entry.items():
            if not isinstance(value, str):
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
        console(
            'Press ^D or type \'exit\' to continue. Type \'continue\' to continue non-interactive execution.'
        )
        console(
            'Task \'%s\' has %s entries, enter regexp to see what matches it.'
            % (task.name, len(task.entries))
        )
        while True:
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
                        console(
                            'Title: %-40s URL: %-30s From: %s'
                            % (entry['title'], entry['url'], field)
                        )
                        count += 1
                except re.error:
                    console('Invalid regular expression')
                    break
            console('%s of %s entries matched' % (count, len(task.entries)))
        console('Bye!')


@event('plugin.register')
def register_plugin():
    # This plugin runs on task phases, but should not be allowed in the config, so we do not declare the 'task'
    # interface. This may break if we start checking for the task interface for more than just config schemas.
    plugin.register(PluginTryRegexp, '--try-regexp', builtin=True, interfaces=[], api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--try-regexp',
        action='store_true',
        dest='try_regexp',
        default=False,
        help='try regular expressions interactively',
    )
