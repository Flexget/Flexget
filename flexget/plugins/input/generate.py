from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget import validator

log = logging.getLogger(__name__.rsplit('.')[-1])


class Generate(object):
    """Generates n number of random entries. Used for debugging purposes."""

    def validator(self):
        return validator.factory('integer')

    def on_task_input(self, task, config):
        amount = config or 0  # hackily makes sure it's an int value
        for i in range(amount):
            entry = Entry()
            import string
            import random
            entry['url'] = 'http://localhost/generate/%s/%s' % (i, ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)]))
            entry['title'] = ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
            entry['description'] = ''.join([random.choice(string.letters + string.digits) for x in range(1, 1000)])
            task.entries.append(entry)


@event('plugin.register')
def register_plugin():
    plugin.register(Generate, 'generate', api_ver=2, debug=True)
