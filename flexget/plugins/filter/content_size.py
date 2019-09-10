from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from sys import maxsize

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once

log = logging.getLogger('content_size')


class FilterContentSize(object):
    schema = {
        'type': 'object',
        'properties': {
            'min': {'type': 'number'},
            'max': {'type': 'number'},
            'strict': {'type': 'boolean', 'default': True},
        },
        'additionalProperties': False,
    }

    def process_entry(self, task, entry, config, remember=True):
        """Rejects this entry if it does not pass content_size requirements. Returns true if the entry was rejected."""
        if 'content_size' in entry:
            size = entry['content_size']
            log.debug('%s size %s MB' % (entry['title'], size))
            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if size < config.get('min', 0):
                log_once('Entry `%s` too small, rejecting' % entry['title'], log)
                entry.reject(
                    'minimum size %s MB, got %s MB' % (config['min'], size), remember=remember
                )
                return True
            if size > config.get('max', maxsize):
                log_once('Entry `%s` too big, rejecting' % entry['title'], log)
                entry.reject(
                    'maximum size %s MB, got %s MB' % (config['max'], size), remember=remember
                )
                return True

    @plugin.priority(130)
    def on_task_filter(self, task, config):
        # Do processing on filter phase in case input plugin provided the size
        for entry in task.entries:
            self.process_entry(task, entry, config, remember=False)

    @plugin.priority(150)
    def on_task_modify(self, task, config):
        if task.options.test or task.options.learn:
            log.info(
                'Plugin is partially disabled with --test and --learn because size information may not be '
                'available'
            )
            return

        num_rejected = len(task.rejected)
        for entry in task.accepted:
            if 'content_size' in entry:
                self.process_entry(task, entry, config)
            elif config['strict']:
                log.debug(
                    'Entry %s size is unknown, rejecting because of strict mode (default)'
                    % entry['title']
                )
                log.info('No size information available for %s, rejecting' % entry['title'])
                if 'file' not in entry:
                    entry.reject('no size info available nor file to read it from', remember=True)
                else:
                    entry.reject('no size info available from downloaded file', remember=True)

        if len(task.rejected) > num_rejected:
            # Since we are rejecting after the filter event,
            # re-run this task to see if there is an alternate entry to accept
            task.rerun()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterContentSize, 'content_size', api_ver=2)
