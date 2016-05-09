from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import csv

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

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

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'values': {
                'type': 'object',
                'additionalProperties': {'type': 'integer'},
                'required': ['title', 'url']
            }
        },
        'required': ['url', 'values'],
        'additionalProperties': False
    }

    @cached('csv')
    def on_task_input(self, task, config):
        entries = []
        try:
            r = task.requests.get(config['url'])
        except RequestException as e:
            raise plugin.PluginError('Error fetching `%s`: %s' % (config['url'], e))
        # CSV module needs byte strings, we'll convert back to unicode later
        page = r.text.encode('utf-8').splitlines()
        for row in csv.reader(page):
            if not row:
                continue
            entry = Entry()
            for name, index in list(config.get('values', {}).items()):
                try:
                    # Convert the value back to unicode
                    entry[name] = row[index - 1].decode('utf-8').strip()
                except IndexError:
                    raise plugin.PluginError('Field `%s` index is out of range' % name)

            entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputCSV, 'csv', api_ver=2)
