from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import parse_timedelta

from dateutil.parser import parse as dateutil_parse

log = logging.getLogger('age')


class Age(object):
    """
        Rejects/accepts entries based on date in specified entry field

        Example:

          age:
            field: 'accessed'  # 'accessed' is a field set from filesystem plugin
            age: '7 days'
            action: 'accept'
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': {'type': 'string'},
            'action': {'type': 'string', 'enum': ['accept', 'reject']},
            'age': {'type': 'string', 'format': 'interval'},
        },
        'required': ['field', 'action', 'age'],
        'additionalProperties': False,
    }

    def on_task_filter(self, task, config):
        for entry in task.entries:
            field = config['field']
            if field not in entry:
                entry.fail('Field {0} does not exist'.format(field))
                continue

            field_value = entry[field]

            if isinstance(field_value, datetime):
                field_date = field_value
            elif isinstance(field_value, float):
                field_date = datetime.fromtimestamp(field_value)
            elif isinstance(field_value, str):
                try:
                    field_date = dateutil_parse(entry[field])
                except ValueError:
                    log.warning(
                        'Entry %s ignored: %s is not a valid date', entry['title'], field_value
                    )
                    continue
            else:
                log.warning(
                    'Entry %s ignored: %s is not a valid date', entry['title'], field_value
                )
                continue

            age_cutoff = datetime.now() - parse_timedelta(config['age'])

            if field_date < age_cutoff:
                info_string = 'Date in field `{0}` is older than {1}'.format(field, config['age'])
                if config['action'] == 'accept':
                    entry.accept(info_string)
                else:
                    entry.reject(info_string)
                log.debug(
                    'Entry %s was %sed because date in field `%s` is older than %s',
                    entry['title'],
                    config['action'],
                    field,
                    config['age'],
                )


@event('plugin.register')
def register_plugin():
    plugin.register(Age, 'age', api_ver=2)
