from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import ReList
from flexget.config_schema import one_or_more

log = logging.getLogger('regex_extract')


class RegexExtract(object):
    """
    Updates an entry with the values of regex matched named groups

    Usage:

      regex_extract:
        field: <string>
        regex:
          - <regex>
        [prefix]: <string>


    Example:

      regex_extract:
        prefix: f1_
        field: title
        regex:
          - Formula\.?1.(?P<location>*?)

    """

    schema = {
        'type': 'object',
        'properties': {
            'prefix': {'type': 'string'},
            'field': {'type': 'string'},
            'regex': one_or_more({'type': 'string', 'format': 'regex'}),
        },
    }

    def on_task_start(self, task, config):
        regex = config.get('regex')
        if isinstance(regex, basestring):
            regex = [regex]
        self.regex_list = ReList(regex)

        # Check the regex
        try:
            for rx in self.regex_list:
                pass
        except re.error as e:
            raise plugin.PluginError('Error compiling regex: %s' % str(e))

    def on_task_modify(self, task, config):

        prefix = config.get('prefix')
        modified = 0

        for entry in task.entries:
            for rx in self.regex_list:
                entry_field = entry.get('title')
                log.debug('Matching %s with regex: %s' % (entry_field, rx))
                try:
                    match = rx.match(entry_field)
                except re.error as e:
                    raise plugin.PluginError('Error encountered processing regex: %s' % str(e))
                if match:
                    log.debug('Successfully matched %s' % entry_field)
                    data = match.groupdict()
                    if prefix:
                        for key in list(data.keys()):
                            data[prefix + key] = data[key]
                            del data[key]
                    log.debug('Values added to entry: %s' % data)
                    entry.update(data)
                    modified += 1

        log.info('%d entries matched and modified' % modified)


@event('plugin.register')
def register_plugin():
    plugin.register(RegexExtract, 'regex_extract', api_ver=2)
