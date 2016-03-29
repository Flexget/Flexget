from __future__ import unicode_literals, division, absolute_import
import logging
import os
import sys
from datetime import datetime

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('file_age')


class FileAge(object):
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
            'stat': {'type': 'string', 'enum': ['access', 'modified', 'created']},
            'reject': {'type': 'boolean', 'default': True},
            'age': {'type': 'string', 'format': 'interval'}
        },
        'required': ['stat', 'age'],
        'additionalProperties': False
    }

    def on_task_filter(self, task, config):
        for entry in task.entries:
            if 'location' not in entry:
                log.debug('Entry %s is not a local file. Skipping.', entry['title'])
                continue
            filepath = entry['location']
            if config['stat'] == 'created' and not sys.platform.startswith('win'):
                log.warning('File creation time is not available in *nix OS and defaults to modification time.')
            file_stats = {}
            file_stats['access'] = datetime.fromtimestamp(os.path.getatime(filepath))
            file_stats['modified'] = datetime.fromtimestamp(os.path.getmtime(filepath))
            file_stats['created'] = datetime.fromtimestamp(os.path.getctime(filepath))

            log.debug('Found following stats for %s: access=%s, modified=%s, created=%s', filepath,
                      file_stats['access'], file_stats['modified'], file_stats['created'])
            age_cutoff = datetime.now() - parse_timedelta(config['age'])

            if file_stats[config['stat']] < age_cutoff:
                info_string = 'Last %s time is older than %s', config['stat'], config['age']
                if config['reject']:
                    log.debug('File %s was rejected because its %s time is older than %s', filepath, config['stat'],
                              config['age'])
                    entry.reject(info_string)
                else:
                    log.debug('File %s was accepted because its %s time is older than %s', filepath, config['stat'],
                              config['age'])
                    entry.accept(info_string)


@event('plugin.register')
def register_plugin():
    plugin.register(FileAge, 'file_age', api_ver=2)
