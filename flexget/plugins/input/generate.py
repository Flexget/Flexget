from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger(__name__.rsplit('.')[-1])


class Generate(object):
    """Generates n number of random entries. Used for debugging purposes."""

    schema = {'type': 'integer'}

    def on_task_input(self, task, config):
        amount = config or 0  # hackily makes sure it's an int value
        entries = []
        for i in range(amount):
            entry = Entry()
            import string
            import random
            entry['url'] = 'http://localhost/generate/%s/%s' % (
                i,
                ''.join([random.choice(string.ascii_letters + string.digits) for x in range(1, 30)]))
            entry['title'] = ''.join([random.choice(string.ascii_letters + string.digits) for x in range(1, 30)])
            entry['description'] = ''.join([random.choice(string.ascii_letters + string.digits) for x in range(1, 1000)])
            entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Generate, 'generate', api_ver=2, debug=True)
