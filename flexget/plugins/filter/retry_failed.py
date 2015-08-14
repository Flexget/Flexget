from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Unicode, DateTime
from sqlalchemy.schema import Index

from flexget import db_schema, options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.utils.tools import parse_timedelta
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema

SCHEMA_VER = 3

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
        failed = table_schema('failed', session)
        Index('failed_title_url', failed.c.title, failed.c.url, failed.c.count).create()
        ver = 1
    if ver == 1:
        table_add_column('failed', 'reason', Unicode, session)
        ver = 2
    if ver == 2:
        table_add_column('failed', 'retry_time', DateTime, session)
        ver = 3
    return ver


class FailedEntry(Base):
    __tablename__ = 'failed'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String)
    tof = Column(DateTime)
    reason = Column(Unicode)
    count = Column(Integer, default=1)
    retry_time = Column(DateTime)

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

    def __init__(self):
        try:
            self.backlog = plugin.get_plugin_by_name('backlog')
        except plugin.DependencyError:
            log.warning('Unable utilize backlog plugin, failed entries may not be retried properly.')

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
        return timedelta(seconds=retry_secs)

    @plugin.priority(-255)
    def on_task_input(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        for entry in task.all_entries:
            entry.on_fail(self.add_failed, config=config)

    def add_failed(self, entry, reason=None, config=None, **kwargs):
        """Adds entry to internal failed list, displayed with --failed"""
        # Make sure reason is a string, in case it is set to an exception instance
        reason = unicode(reason) or 'Unknown'
        with Session() as session:
            # query item's existence
            item = session.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                filter(FailedEntry.url == entry['original_url']).first()
            if not item:
                item = FailedEntry(entry['title'], entry['original_url'], reason)
                item.count = 0
            retry_time = self.retry_time(item.count, config)
            item.retry_time = datetime.now() + retry_time
            item.count += 1
            item.tof = datetime.now()
            item.reason = reason
            session.merge(item)
            log.debug('Marking %s in failed list. Has failed %s times.' % (item.title, item.count))
            if self.backlog and item.count <= config['max_retries']:
                self.backlog.instance.add_backlog(entry.task, entry, amount=retry_time, session=session)
            entry.task.rerun()
            # limit item number to 25
            for row in session.query(FailedEntry).order_by(FailedEntry.tof.desc())[25:]:
                session.delete(row)

    @plugin.priority(255)
    def on_task_filter(self, task, config):
        if config is False:
            return
        config = self.prepare_config(config)
        max_count = config['max_retries']
        for entry in task.entries:
            item = task.session.query(FailedEntry).filter(FailedEntry.title == entry['title']).\
                filter(FailedEntry.url == entry['original_url']).first()
            if item:
                if item.count > max_count:
                    entry.reject('Has already failed %s times in the past. (failure reason: %s)' %
                                 (item.count, item.reason))
                elif item.retry_time and item.retry_time > datetime.now():
                    entry.reject('Waiting before retrying entry which has failed in the past. (failure reason: %s)' %
                                 item.reason)


def do_cli(manager, options):
    if options.failed_action == 'list':
        list_failed()
    elif options.failed_action == 'clear':
        clear_failed(manager)


def list_failed():
    session = Session()
    try:
        results = session.query(FailedEntry).all()
        if not results:
            console('No failed entries recorded')
        for entry in results:
            console('%16s - %s - %s times - %s' %
                    (entry.tof.strftime('%Y-%m-%d %H:%M'), entry.title, entry.count, entry.reason))
    finally:
        session.close()


def clear_failed(manager):
    session = Session()
    try:
        results = session.query(FailedEntry).delete()
        console('Cleared %i items.' % results)
        session.commit()
        if results:
            manager.config_changed()
    finally:
        session.close()


@event('plugin.register')
def register_plugin():
    plugin.register(PluginFailed, 'retry_failed', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('failed', do_cli, help='list or clear remembered failures')
    subparsers = parser.add_subparsers(dest='failed_action', metavar='<action>')
    subparsers.add_parser('list', help='list all the entries that have had failures')
    subparsers.add_parser('clear', help='clear all failures from database, so they can be retried')
