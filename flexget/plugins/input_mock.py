import logging
from flexget.feed import Entry

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('input_mock')

class InputMock:

    """
        Allows adding mock input entries. Example:
        
        input_mock:
          - {title: foobar, url: http://some.com }
          - {title: mock, url: http://another.com }
    """

    def register(self, manager, parser):
        manager.register('input_mock', debug_plugin=True)
        
    def validator(self):
        from flexget import validator
        container = validator.factory('list')
        entry = container.accept('dict')
        entry.accept('url', key='url', required=True)
        entry.accept('text', key='title', required=True)
        entry.accept_any_key('text')
        entry.accept_any_key('number')
        return container

    def feed_input(self, feed):
        config = feed.config.get('input_mock', [])
        for line in config:
            entry = Entry()
            for k,v in line.iteritems():
                entry[k] = v
            feed.entries.append(entry)
