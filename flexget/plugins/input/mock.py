"""Plugin for filesystem feeds."""
import logging
from flexget.feed import Entry
from flexget import plugin

log = logging.getLogger('mock')


# XXX: Shouldn't mock be "debug"?
class Mock(plugin.Plugin):
    """
        Allows adding mock input entries. Example:

        mock:
          - {title: foobar, url: http://some.com }
          - {title: mock, url: http://another.com }

        If url is not given a random url pointing to localhost will be generated.
    """

    def validator(self):
        from flexget import validator
        container = validator.factory('list')
        entry = container.accept('dict')
        entry.accept('text', key='title', required=True)
        entry.accept('url', key='url')
        entry.accept_any_key('text')
        entry.accept_any_key('number')
        entry.accept_any_key('list').accept('any')
        return container

    def on_feed_input(self, feed, config):
        entries = []
        for line in config:
            entry = Entry()
            for k, v in line.iteritems():
                entry[k] = v
            # no url specified, add random one (ie. test)
            if not 'url' in entry:
                import string
                import random
                entry['url'] = 'http://localhost/mock/%s' % ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
            entries.append(entry)
        return entries
