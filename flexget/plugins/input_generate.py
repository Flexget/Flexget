import logging
from flexget.feed import Entry
from flexget.plugin import *

log = logging.getLogger('generate')


class InputGenerate(object):
    """Generates n number of random entries. Used for debugging purposes."""

    def validator(self):
        from flexget import validator
        return validator.factory('integer')

    def on_feed_input(self, feed):
        amount = feed.config.get('generate', 0)
        for i in range(amount):
            entry = Entry()
            import string
            import random
            entry['url'] = 'http://localhost/generate/%s/%s' % (i, ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)]))
            entry['title'] = ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
            feed.entries.append(entry)

register_plugin(InputGenerate, 'generate', debug=True)
