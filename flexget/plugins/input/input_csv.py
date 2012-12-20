from __future__ import unicode_literals, division, absolute_import
import logging
import csv
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet
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

    @cached('csv')
    @internet(log)
    def on_task_input(self, task, config):
        entries = []
        page = urlopener(config['url'], log)
        for row in csv.reader(page):
            if not row:
                continue
            entry = Entry()
            for name, index in config.get('values', {}).items():
                try:
                    entry[name] = row[index - 1]
                except IndexError:
                    raise Exception('Field `%s` index is out of range' % name)
            entries.append(entry)
        return entries

register_plugin(InputCSV, 'csv', api_ver=2)
