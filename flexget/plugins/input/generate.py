import logging
from flexget.entry import Entry
from flexget import plugin, validator

# Global constants
log = logging.getLogger(__name__.rsplit('.')[-1])


class Generate(plugin.DebugPlugin):
    """Generates n number of random entries. Used for debugging purposes."""

    def validator(self):
        return validator.factory('integer')

    def on_task_input(self, task, config):
        amount = config or 0 # make sure it's an int, and not None etc.
        for i in range(amount):
            entry = Entry()
            import string
            import random
            entry['url'] = 'http://localhost/generate/%s/%s' % (i, ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)]))
            entry['title'] = ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
            entry['description'] = ''.join([random.choice(string.letters + string.digits) for x in range(1, 1000)])
            task.entries.append(entry)
