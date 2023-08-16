from typing import Optional, Tuple

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.tools import format_filesize, parse_filesize

logger = logger.bind(name='content_size')


class FilterContentSize:
    schema = {
        'type': 'object',
        'properties': {
            'min': {'type': ['number', 'string'], 'format': 'size'},
            'max': {'type': ['number', 'string'], 'format': 'size'},
            'strict': {'type': 'boolean', 'default': True},
        },
        'additionalProperties': False,
    }

    @staticmethod
    def process_config(config: dict) -> Tuple[Optional[int], Optional[int]]:
        def _parse_config_size(size):
            if isinstance(size, (int, float)):
                return size * 1024**2
            if isinstance(size, str):
                return parse_filesize(size)
            return None

        return _parse_config_size(config.get('min')), _parse_config_size(config.get('max'))

    def process_entry(self, task, entry, config, remember=True):
        """Rejects this entry if it does not pass content_size requirements. Returns true if the entry was rejected."""
        if 'content_size' in entry:
            min_size, max_size = self.process_config(config)
            size = entry['content_size']
            logger.debug('{} size {}', entry['title'], format_filesize(size))
            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if min_size is not None and size < min_size:
                log_once('Entry `%s` too small, rejecting' % entry['title'], logger)
                entry.reject(
                    f'minimum size {format_filesize(min_size)}, got {format_filesize(size)}',
                    remember=remember,
                )
                return True
            if max_size is not None and size > max_size:
                log_once('Entry `%s` too big, rejecting' % entry['title'], logger)
                entry.reject(
                    f'maximum size {format_filesize(max_size)}, got {format_filesize(size)}',
                    remember=remember,
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
            logger.info(
                'Plugin is partially disabled with --test and --learn because size information may not be '
                'available'
            )
            return

        num_rejected = len(task.rejected)
        for entry in task.accepted:
            if 'content_size' in entry:
                self.process_entry(task, entry, config)
            elif config['strict']:
                logger.debug(
                    'Entry {} size is unknown, rejecting because of strict mode (default)',
                    entry['title'],
                )
                logger.info('No size information available for {}, rejecting', entry['title'])
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
