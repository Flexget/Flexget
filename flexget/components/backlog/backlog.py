from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from datetime import datetime

from sqlalchemy import Index

from flexget import plugin
from flexget.components.backlog.db import log, BacklogEntry, get_entries, clear_entries
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import with_session
from flexget.utils.tools import parse_timedelta


class InputBacklog(object):
    """
    Keeps task history for given amount of time.

    Example::

      backlog: 4 days

    Rarely useful for end users, mainly used by other plugins.
    """

    schema = {'type': 'string', 'format': 'interval'}

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_input(self, task, config):
        # Get a list of entries to inject
        injections = self.get_injections(task)
        # Take a snapshot of the entries' states after the input event in case we have to store them to backlog
        for entry in task.entries + injections:
            entry.take_snapshot('after_input')
        if config:
            # If backlog is manually enabled for this task, learn the entries.
            self.learn_backlog(task, config)
        # Return the entries from backlog that are not already in the task
        return injections

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_metainfo(self, task, config):
        # Take a snapshot of any new entries' states before metainfo event in case we have to store them to backlog
        # This is really a hack to avoid unnecessary lazy lookups causing db locks. Ideally, saving a snapshot
        # should not cause lazy lookups, but we currently have no other way of saving a lazy field than performing its
        # action.
        # https://github.com/Flexget/Flexget/issues/1000
        for entry in task.entries:
            snapshot = entry.snapshots.get('after_input')
            if snapshot:
                continue
            entry.take_snapshot('after_input')

    def on_task_abort(self, task, config):
        """Remember all entries until next execution when task gets aborted."""
        if task.entries:
            log.debug('Remembering all entries to backlog because of task abort.')
            self.learn_backlog(task)

    @with_session
    def add_backlog(self, task, entry, amount='', session=None):
        """Add single entry to task backlog

        If :amount: is not specified, entry will only be injected on next execution."""
        snapshot = entry.snapshots.get('after_input')
        if not snapshot:
            if task.current_phase != 'input':
                # Not having a snapshot is normal during input phase, don't display a warning
                log.warning(
                    'No input snapshot available for `%s`, using current state' % entry['title']
                )
            snapshot = entry
        expire_time = datetime.now() + parse_timedelta(amount)
        backlog_entry = (
            session.query(BacklogEntry)
            .filter(BacklogEntry.title == entry['title'])
            .filter(BacklogEntry.task == task.name)
            .first()
        )
        if backlog_entry:
            # If there is already a backlog entry for this, update the expiry time if necessary.
            if backlog_entry.expire < expire_time:
                log.debug('Updating expiry time for %s' % entry['title'])
                backlog_entry.expire = expire_time
        else:
            log.debug('Saving %s' % entry['title'])
            backlog_entry = BacklogEntry()
            backlog_entry.title = entry['title']
            backlog_entry.entry = snapshot
            backlog_entry.task = task.name
            backlog_entry.expire = expire_time
            session.add(backlog_entry)

    def learn_backlog(self, task, amount=''):
        """Learn current entries into backlog. All task inputs must have been executed."""
        with Session() as session:
            for entry in task.entries:
                self.add_backlog(task, entry, amount, session=session)

    @with_session
    def get_injections(self, task, session=None):
        """Insert missing entries from backlog."""
        entries = []
        for backlog_entry in get_entries(task=task.name, session=session):
            entry = backlog_entry.entry

            # this is already in the task
            if task.find_entry(title=entry['title'], url=entry['url']):
                continue
            log.debug('Restoring %s' % entry['title'])
            entries.append(entry)
        if entries:
            log.verbose('Added %s entries from backlog' % len(entries))

        # purge expired
        purged = clear_entries(task=task.name, all=False, session=session)
        log.debug('%s entries purged from backlog' % purged)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputBacklog, 'backlog', builtin=True, api_ver=2)
