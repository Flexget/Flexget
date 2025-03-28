"""Plugin for mocking task data."""

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='mock')


class Mock:
    """Allows adding mock input entries.

    Example::

      mock:
        - {title: foobar, url: http://some.com }
        - {title: mock, url: http://another.com }
        - Title Only

    If url is not given a random url pointing to localhost will be generated.
    """

    schema = {
        'type': 'array',
        'items': {
            'oneOf': [
                {'type': 'string'},
                {
                    'type': 'object',
                    'properties': {'title': {'type': 'string'}, 'url': {'type': 'string'}},
                    'required': ['title'],
                },
            ],
        },
    }

    def on_task_input(self, task, config):
        entries = []
        for line in config:
            entry = Entry(line) if isinstance(line, dict) else Entry(title=line)
            # no url specified, add random one based on title (ie. test)
            if 'url' not in entry:
                entry['url'] = 'mock://localhost/mock/{}'.format(hash(entry['title']))
            entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Mock, 'mock', api_ver=2)
