from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Unicode, DateTime
from sqlalchemy.schema import Index, MetaData
from flexget import db_schema
from flexget.plugin import register_plugin, register_parser_option, priority, DependencyError, get_plugin_by_name
from flexget.manager import Session
from flexget.utils.tools import console, parse_timedelta
from flexget.utils.sqlalchemy_utils import table_add_column

SCHEMA_VER = 2

log = logging.getLogger('failed')
Base = db_schema.versioned_base('failed', SCHEMA_VER)


@db_schema.upgrade('failed')
def upgrade(ver, session):
    if ver is None:
        # add count column
        table_add_column('failed', 'count', Integer, session, default=1)
        ver = 0
    if ver == 0:
        # define an index
        log.info('Adding database index ...')
        meta = MetaData(bind=session.connection(), reflect=True)
        failed = meta.tables['failed']
        Index('failed_title_url', failed.c.title, failed.c.url, failed.c.count).create()
        ver = 1
    if ver == 1:
        table_add_column('failed', 'reason', Unicode, session)
        ver = 2
    return ver


class FailedEntry(Base):
    __tablename__ = 'failed'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String)
    tof = Column(DateTime)
    reason = Column(Unicode)
    count = Column(Integer, default=1)

    def __init__(self, title, url, reason=None):
        self.title = title
        self.url = url
        self.reason = reason
        self.tof = datetime.now()

    def __str__(self):
        return '<Failed(title=%s)>' % self.title

# create indexes, used when creating tables
columns = Base.metadata.tables['failed'].c
Index('failed_title_url', columns.title, columns.url, columns.count)


class PluginFailed(object):
    """Provides tracking for failures and related commandline utilities."""

    def on_process_start(self, task, config):
        if task.manager.options.failed:
            task.manager.disable_tasks()
            self.print_failed()
            return
        if task.manager.options.clear_failed:
            task.manager.disable_tasks()
            if self.clear_failed():
                task.manager.config_changed()
            return

    @priority(-255)
    def on_task_input(self, task, config):
        for entry in task.all_entries:
            entry.on_fail(self.add_failed)

    def print_failed(self):
        """Parameter --failed"""

        failed = Session()
        try:
            results = failed.query(FailedEntry).all()
            if not results:
                console('No failed entries recorded')
            for entry in results:
                console('%16s - %s - %s times - %s' %
                        (entry.tof.strftime('%Y-%m-%d %H:%M'), entry.title, entry.count, entry.reason))
        finally:
            failed.close()

    def add_failed(self, entry, reason=None, **kwargs):
        """Adds entry to internal failed list, displayed with --failed"""
        reason = reason or 'Unknown'
        failed = Session()
        try:
            # query item's existence
            item = failed.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                filter(FailedEntry.url == entry['original_url']).first()
            if not item:
                item = FailedEntry(entry['title'], entry['original_url'], reason)
            else:
                item.count += 1
                item.tof = datetime.now()
                item.reason = reason
            failed.merge(item)
            log.debug('Marking %s in failed list. Has failed %s times.' % (item.title, item.count))

            # limit item number to 25
            for row in failed.query(FailedEntry).order_by(FailedEntry.tof.desc())[25:]:
                failed.delete(row)
            failed.commit()
        finally:
            failed.close()

    def clear_failed(self):
        """
        Clears list of failed entries

        :return: The number of entries cleared.
        """
        session = Session()
        try:
            results = session.query(FailedEntry).delete()
            console('Cleared %i items.' % results)
            session.commit()
            return results
        finally:
            session.close()


class FilterRetryFailed(object):
    """Stores failed entries for trying again after a certain interval,
    rejects them after they have failed too many times."""

    def __init__(self):
        self.backlog = None

    schema = {
        "oneOf": [
            # Allow retry_failed: no form to turn off plugin altogether
            {"type": "boolean"},
            {
                "type": "object",
                "properties": {
                    "retry_time": {"type": "string", "format": "interval", "default": "1 hour"},
                    "max_retries": {"type": "integer", "minimum": 0, "default": 3},
                    "retry_time_multiplier": {
                        # Allow turning off the retry multiplier with 'no' as well as 1
                        "oneOf": [{"type": "number", "minimum": 0}, {"type": "boolean"}],
                        "default": 1.5
                    }
                },
                "additionalProperties": False
            }
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

    def on_process_start(self, task, config):
        try:
            self.backlog = get_plugin_by_name('backlog').instance
        except DependencyError:
            log.warning('Unable utilize backlog plugin, failed entries may not be retried properly.')

    @priority(255)
    def on_task_filter(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        max_count = config['max_retries']
        for entry in task.entries:
            item = task.session.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                filter(FailedEntry.url == entry['original_url']).\
                filter(FailedEntry.count > max_count).first()
            if item:
                entry.reject('Has already failed %s times in the past' % item.count)

    def on_task_exit(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        base_retry_time = parse_timedelta(config['retry_time'])
        retry_time_multiplier = config['retry_time_multiplier']
        for entry in task.failed:
            item = task.session.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                filter(FailedEntry.url == entry['original_url']).first()
            if item:
                # Do not count the failure on this run when adding additional retry time
                fail_count = item.count - 1
                # Don't bother saving this if it has met max retries
                if fail_count >= config['max_retries']:
                    continue
                # Timedeltas do not allow floating point multiplication. Convert to seconds and then back to avoid this.
                base_retry_secs = base_retry_time.days * 86400 + base_retry_time.seconds
                retry_secs = base_retry_secs * (retry_time_multiplier ** fail_count)
                retry_time = timedelta(seconds=retry_secs)
            else:
                retry_time = base_retry_time
            if self.backlog:
                self.backlog.add_backlog(task, entry, amount=retry_time)
            if retry_time:
                fail_reason = item.reason if item else entry.get('reason', 'unknown')
                entry.reject(reason='Waiting before trying failed entry again. (failure reason: %s)' %
                    fail_reason, remember_time=retry_time)
                # Cause a task rerun, to look for alternate releases
                task.rerun()

register_plugin(PluginFailed, '--failed', builtin=True, api_ver=2)
register_plugin(FilterRetryFailed, 'retry_failed', builtin=True, api_ver=2)
register_parser_option('--failed', action='store_true', dest='failed', default=0,
                       help='List recently failed entries.')
register_parser_option('--clear', action='store_true', dest='clear_failed', default=0,
                       help='Clear recently failed list.')
