from __future__ import unicode_literals, division, absolute_import
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
            field: 'access'  # 'access' is a field set from filesystem plugin
            age: '7 days'
            action: 'accept'
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': {'type': 'string'},
            'action': {'type': 'string', 'enum': ['accept', 'reject']},
            'age': {'type': 'string', 'format': 'interval'}
        },
        'required': ['field', 'action', 'age'],
        'additionalProperties': False
    }

    def on_task_filter(self, task, config):
        for entry in task.entries:
            field = config['field']
            if field not in entry:
                entry.fail('Field {0} does not exist'.format(field))
                continue

            val = entry[field]
            age_cutoff = datetime.now() - parse_timedelta(config['age'])

            field_date = datetime.fromtimestamp(val) if isinstance(val, float) else dateutil_parse(val)
            if field_date < age_cutoff:
                info_string = 'Date in field {0} is older than {1}'.format(field, config['age'])
                if config['action'] == 'accept':
                    entry.accept(info_string)
                else:
                    entry.reject(info_string)
                log.debug('Entry %s was %sed because date in field %s is older than %s', entry['title'],
                          config['action'], field, config['age'])


@event('plugin.register')
def register_plugin():
    plugin.register(Age, 'age', api_ver=2)
