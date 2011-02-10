import logging
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.tools import str_to_boolean

log = logging.getLogger('inject')


class InputInject(object):
    """
        Allows injecting imaginary entry for FlexGet to process.

        Syntax:

        --inject <TITLE> [URL] [ACCEPTED] [IMMORTAL]

        Random url will be generated. All other inputs from freed(s) are disabled.


        Example use:

        flexget --inject "Some.Series.S02E12.Imaginary" --feed my-series --learn

        This would inject imaginary series into a single feed and learn it as a downloaded,
        assuming feed accepts the injected entry.

    """

    def validator(self):
        from flexget import validator
        return validator.factory('any')

    options = {}

    @staticmethod
    def optik_series(option, opt, value, parser):
        """--inject <TITLE> [URL] [ACCEPTED] [IMMORTAL]"""
        #InputInject.options
        index = 0
        for arg in parser.rargs:
            if arg.startswith('--'):
                break
            index += 1
            if index == 1:
                InputInject.options['title'] = arg
            elif index == 2:
                InputInject.options['url'] = arg
            elif index == 3:
                if arg.lower() == 'accept':
                    InputInject.options['accept'] = True
                else:
                    InputInject.options['accept'] = str_to_boolean(arg)
            elif index == 4:
                if arg.lower() == 'force':
                    InputInject.options['force'] = True
                else:
                    InputInject.options['force'] = str_to_boolean(arg)
            else:
                log.critical('Unknown --inject parameter %s' % arg)

    @priority(255)
    def on_feed_input(self, feed):
        if not InputInject.options:
            return

        # disable other inputs
        log.info('Disabling the rest of the input phase.')
        feed.disable_phase('input')

        # create our injected entry
        import string
        import random

        entry = Entry()
        entry['injected'] = True
        entry['title'] = InputInject.options['title']
        if 'url' in InputInject.options:
            entry['url'] = InputInject.options['url']
        else:
            entry['url'] = 'http://localhost/inject/%s' % ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
        if InputInject.options.get('force', False):
            log.debug('setting injection as immortal')
            entry['immortal'] = True

        feed.entries.append(entry)

        if InputInject.options.get('accept', False):
            log.debug('accepting the injection')
            feed.accept(entry, '--inject accepted')


register_plugin(InputInject, '--inject', debug=True, builtin=True)

register_parser_option('--inject', action='callback', callback=InputInject.optik_series,
                       help='Injects entry to all executed feeds: <TITLE> [URL] [ACCEPT] [FORCE]')
