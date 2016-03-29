from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('age')


class Age(object):
    """
        Rejects/accepts files based on file metadata

        Example::

          file_age:
            stat: 'access'
            age: '7 days'
    """

    schema = {
        'type': 'object',
        'properties': {
            'field': {'type': 'string'},
            'action': {'type': 'string', 'enum': ['accept', 'reject']},
            'amount': {'type': 'string', 'format': 'interval'}
        },
        'required': ['field', 'action', 'amount'],
        'additionalProperties': False
    }

    def on_task_filter(self, task, config):
        for entry in task.entries:
            field = config['field']
            if field not in entry:
                entry.fail('Field {0} does not exist'.format(field))
                continue

            age_cutoff = datetime.now() - parse_timedelta(config['amount'])

            if entry[field] < age_cutoff:
                info_string = 'Date in field {0} is older than {1}'.format(field, config['amount'])
                if config['action'] == 'accept':
                    entry.accept(info_string)
                else:
                    entry.reject(info_string)
                log.debug('Entry %s was %sed because date in field %s is older than %s', entry['title'],
                          config['action'], field, config['amount'])


@event('plugin.register')
def register_plugin():
    plugin.register(Age, 'age', api_ver=2)
