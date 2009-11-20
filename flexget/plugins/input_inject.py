import logging
from flexget.feed import Entry
from flexget.plugin import *

log = logging.getLogger('inject')


class InputInject:
    """
        Allows injecting imaginary entry for FlexGet to process.
        
        Syntax:
        
        --inject <title> 
        
        Random url will be generated. All other inputs are disabled.

        
        Example use:
        
        flexget --inject "Some.Series.S02E12.Imaginary" --feed my-series --learn
        
        This would inject imaginary series into a single feed and learn it as a downloaded,
        assuming feed accepts the injected entry.
        
    """

    def validator(self):
        from flexget import validator
        return validator.factory('any')

    def on_feed_input(self, feed):
        if not feed.manager.options.inject:
            return

        # disable other inputs
        for input in get_plugins_by_event('input'):
            if input.name in feed.config:
                log.info('Disabling plugin %s' % input.name)
                del(feed.config[input.name])
        
        # create our injected entry
        import string
        import random

        entry = Entry()
        entry['injected'] = True
        entry['title'] = feed.manager.options.inject
        entry['url'] = 'http://localhost/inject/%s' % ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
        feed.entries.append(entry)

register_plugin(InputInject, '--inject', debug=True, builtin=True, priorities={'input': 255})

register_parser_option('--inject', action='store', dest='inject', default=False,
                       metavar='TITLE', help='Injects imaginary entry to feed(s).')
