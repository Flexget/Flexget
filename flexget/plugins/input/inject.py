from __future__ import unicode_literals, division, absolute_import
import string
import random
import logging
import yaml
from flexget.entry import Entry
from flexget.plugin import register_plugin, register_parser_option, priority
from flexget.utils.tools import str_to_boolean

log = logging.getLogger('inject')


class InputInject(object):
    """
        Allows injecting imaginary entry for FlexGet to process.

        Syntax:

        --inject <TITLE> [URL] [ACCEPTED] [IMMORTAL]

        Random url will be generated. All other inputs from freed(s) are disabled.


        Example use:

        flexget --inject "Some.Series.S02E12.Imaginary" --task my-series --learn

        This would inject imaginary series into a single task and learn it as a downloaded,
        assuming task accepts the injected entry.

    """

    options = {}

    def parse_arguments(self, arguments):
        """--inject <TITLE> [URL] [ACCEPTED] [IMMORTAL]"""
        options = {}
        for index, arg in enumerate(arguments):
            if index == 0:
                options['entry'] = {'title': arg}
            elif index == 1:
                options['entry']['url'] = arg
            elif '=' in arg:
                field, val = arg.split('=')
                options['entry'][field] = yaml.load(val)
            elif index == 2:
                if arg.lower() == 'accept':
                    options['accept'] = True
                else:
                    options['accept'] = str_to_boolean(arg)
            elif index == 3:
                if arg.lower() == 'force':
                    options['entry']['immortal'] = True
                else:
                    options['entry']['immortal'] = str_to_boolean(arg)
            else:
                log.critical('Unknown --inject parameter %s' % arg)

        return options

    @priority(255)
    def on_task_input(self, task):
        if not task.manager.options.inject:
            return

        options = self.parse_arguments(task.manager.options.inject)

        # disable other inputs
        log.info('Disabling the rest of the input phase.')
        task.disable_phase('input')

        # create our injected entry
        entry = Entry(options['entry'], injected=True)
        if not 'url' in entry:
            entry['url'] = 'http://localhost/inject/%s' % ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
        if entry.get('immortal'):
            log.debug('Injected entry is immortal')

        task.all_entries.append(entry)

        if options.get('accept', False):
            log.debug('accepting the injection')
            entry.accept('--inject accepted')


register_plugin(InputInject, '--inject', debug=True, builtin=True)
register_parser_option('--inject', nargs='+', metavar=('TITLE', 'URL'),
                       help='Injects entry to all executed tasks: <TITLE> [URL] [ACCEPT] [FORCE]')
