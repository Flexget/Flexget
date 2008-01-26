import urllib
import urllib2
import urlparse
import logging
import re

log = logging.getLogger('csv')

class InputCSV:

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
        List of other common (optional) fields can be found from documentation.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='input', keyword='csv', callback=self.run)

    def run(self, feed):
        url = feed.config['csv'].get('url', None)
        if not url: raise Exception('CSV in %s is missing url' % feed.name)
        page = urllib2.urlopen(url)
        for line in page.readlines():
            data = line.split(",")
            print data
            entry = {}
            for name, index in feed.config['csv'].get('values', {}).items():
                try:
                    entry[name] = data[index+1]
                except IndexError, e:
                    raise Exception("Field '%s' index is out of range" % name)
            feed.entries.append(entry)


if __name__ == '__main__':
    import sys
    from test_tools import MockFeed
    import yaml
    logging.basicConfig(level=logging.DEBUG)
    feed = MockFeed()

    # make mock config
    config = {}
    config['url'] = 'http://localhost/test.csv'
    values = {}
    values['url'] = 1
    values['title'] = 3
    config['values'] = values
    feed.config['csv'] = config

    print yaml.dump(feed.config)

    csv = InputCSV()
    csv.run(feed)

    print yaml.dump(feed.entries)
