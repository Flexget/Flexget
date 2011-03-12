import logging
from flexget.feed import Entry
from flexget.plugin import *
from flexget.utils.cached_input import cached
from flexget.utils.tools import urlopener

log = logging.getLogger('csv')


class InputCSV(object):
    """
        Adds support for CSV format. Configuration may seem a bit complex,
        but this has advantage of being universal solution regardless of CSV
        and internal entry fields.

        Configuration format:

        csv:
          url: <url>
          values:
            <field>: <number>

        Example DB-fansubs:

        csv:
          url: http://www.dattebayo.com/t/dump
          values:
            title: 3  # title is in 3th field
            url: 1    # download url is in 1st field

        Fields title and url are mandatory. First field is 1.
        List of other common (optional) fields can be found from wiki.
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('url', key='url', required=True)
        values = config.accept('dict', key='values', required=True)
        values.accept_any_key('integer')
        return config

    @cached('csv', 'url')
    @internet(log)
    def on_feed_input(self, feed):
        url = feed.config['csv'].get('url', None)
        if not url:
            raise Exception('CSV in %s is missing url' % feed.name)
        page = urlopener(url, log)
        for line in page.readlines():
            data = line.split(",")
            entry = Entry()
            for name, index in feed.config['csv'].get('values', {}).items():
                try:
                    entry[name] = data[index-1]
                except IndexError:
                    raise Exception('Field %s index is out of range' % name)
            feed.entries.append(entry)

register_plugin(InputCSV, 'csv')
