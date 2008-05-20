import logging
from feed import Entry

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
        manager.register(event='input', keyword='input_mock', callback=self.run, debug_module=True)

    def run(self, feed):
        config = feed.config.get('input_mock', [])
        for line in config:
            entry = Entry()
            for k,v in line.iteritems():
                entry[k] = v
            feed.entries.append(entry)
