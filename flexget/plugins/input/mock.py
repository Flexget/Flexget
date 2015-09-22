"""Plugin for mocking task data."""
from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('mock')


class Mock(object):
    """
    Allows adding mock input entries.

    Example::

      mock:
        - {title: foobar, url: http://some.com }
        - {title: mock, url: http://another.com }

    If url is not given a random url pointing to localhost will be generated.
    """

    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'url': {'type': 'string'}
            },
            'required': ['title']
        }
    }

    def on_task_input(self, task, config):
        entries = []
        for line in config:
            entry = Entry(line)
            # no url specified, add random one based on title (ie. test)
            if 'url' not in entry:
                entry['url'] = 'mock://localhost/mock/%s' % hash(entry['title'])
            entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Mock, 'mock', api_ver=2)
