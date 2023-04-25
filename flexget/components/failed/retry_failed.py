from datetime import datetime, timedelta

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import parse_timedelta

from . import db

SCHEMA_VER = 3
FAIL_LIMIT = 100

logger = logger.bind(name='failed')


class PluginFailed:
    """
    Records entry failures and stores them for trying again after a certain interval.
    Rejects them after they have failed too many times.

    """

    schema = {
        "oneOf": [
            # Allow retry_failed: no form to turn off plugin altogether
            {"type": "boolean"},
            {
                "type": "object",
                "properties": {
                    "retry_time": {"type": "string", "format": "interval", "default": "1 hour"},
                    "max_retries": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": FAIL_LIMIT,
                        "default": 3,
                    },
                    "retry_time_multiplier": {
                        # Allow turning off the retry multiplier with 'no' as well as 1
                        "oneOf": [{"type": "number", "minimum": 0}, {"type": "boolean"}],
                        "default": 1.5,
                    },
                },
                "additionalProperties": False,
            },
        ]
    }

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {}
        config.setdefault('retry_time', '1 hour')
        config.setdefault('max_retries', 3)
        if config.get('retry_time_multiplier', True) is True:
            # If multiplier is not specified, or is specified as True, use the default
            config['retry_time_multiplier'] = 1.5
        else:
            # If multiplier is False, turn it off
            config['retry_time_multiplier'] = 1
        return config

    def retry_time(self, fail_count, config):
        """Return the timedelta an entry that has failed `fail_count` times before should wait before being retried."""
        base_retry_time = parse_timedelta(config['retry_time'])
        # Timedeltas do not allow floating point multiplication. Convert to seconds and then back to avoid this.
        base_retry_secs = base_retry_time.days * 86400 + base_retry_time.seconds
        retry_secs = base_retry_secs * (config['retry_time_multiplier'] ** fail_count)
        # prevent OverflowError: date value out of range, cap to 30 days
        max = 60 * 60 * 24 * 30
        if retry_secs > max:
            retry_secs = max
        return timedelta(seconds=retry_secs)

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_input(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        for entry in task.all_entries:
            entry.on_fail(self.add_failed, config=config)

    def add_failed(self, entry, reason=None, config=None, **kwargs):
        """Adds entry to internal failed list, displayed with --failed"""
        # Make sure reason is a string, in case it is set to an exception instance
        reason = str(reason) or 'Unknown'
        with Session() as session:
            # query item's existence
            item = (
                session.query(db.FailedEntry)
                .filter(db.FailedEntry.title == entry['title'])
                .filter(db.FailedEntry.url == entry['original_url'])
                .first()
            )
            if not item:
                item = db.FailedEntry(entry['title'], entry['original_url'], reason)
                item.count = 0
            if item.count > FAIL_LIMIT:
                logger.error(
                    "entry with title '{}' has failed over {} times", entry['title'], FAIL_LIMIT
                )
                return
            retry_time = self.retry_time(item.count, config)
            item.retry_time = datetime.now() + retry_time
            item.count += 1
            item.tof = datetime.now()
            item.reason = reason
            session.merge(item)
            logger.debug('Marking {} in failed list. Has failed {} times.', item.title, item.count)
            if item.count <= config['max_retries']:
                plugin.get('backlog', self).add_backlog(
                    entry.task, entry, amount=retry_time, session=session
                )
            entry.task.rerun(plugin='retry_failed')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        max_count = config['max_retries']
        for entry in task.entries:
            item = (
                task.session.query(db.FailedEntry)
                .filter(db.FailedEntry.title == entry['title'])
                .filter(db.FailedEntry.url == entry['original_url'])
                .first()
            )
            if item:
                if item.count > max_count:
                    entry.reject(
                        f'Has already failed {item.count} times in the past. (failure reason: {item.reason})'
                    )
                elif item.retry_time and item.retry_time > datetime.now():
                    entry.reject(
                        'Waiting before retrying entry which has failed in the past. (failure reason: %s)'
                        % item.reason
                    )


@event('plugin.register')
def register_plugin():
    plugin.register(PluginFailed, 'retry_failed', builtin=True, api_ver=2)
