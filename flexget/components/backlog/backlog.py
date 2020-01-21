from datetime import datetime

from loguru import logger

from flexget import plugin
from flexget.components.backlog.db import BacklogEntry, clear_entries, get_entries
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import with_session
from flexget.utils.serialization import serialize
from flexget.utils.tools import parse_timedelta

logger = logger.bind(name='backlog')


class InputBacklog:
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
        if config:
            # If backlog is manually enabled for this task, learn the entries.
            self.learn_backlog(task, config)
        # Return the entries from backlog that are not already in the task
        return injections

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_metainfo(self, task, config):
        # Take a snapshot of any new entries' states before metainfo event in case we have to store them to backlog
        for entry in task.entries:
            entry['_backlog_snapshot'] = serialize(entry)

    def on_task_abort(self, task, config):
        """Remember all entries until next execution when task gets aborted."""
        if task.entries:
            logger.debug('Remembering all entries to backlog because of task abort.')
            self.learn_backlog(task)

    @with_session
    def add_backlog(self, task, entry, amount='', session=None):
        """Add single entry to task backlog

        If :amount: is not specified, entry will only be injected on next execution."""
        snapshot = entry.get('_backlog_snapshot')
        if not snapshot:
            if task.current_phase != 'input':
                # Not having a snapshot is normal during input phase, don't display a warning
                logger.warning(
                    'No input snapshot available for `{}`, using current state', entry['title']
                )
            snapshot = serialize(entry)
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
                logger.debug('Updating expiry time for {}', entry['title'])
                backlog_entry.expire = expire_time
        else:
            logger.debug('Saving {}', entry['title'])
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
            logger.debug('Restoring {}', entry['title'])
            entries.append(entry)
        if entries:
            logger.verbose('Added {} entries from backlog', len(entries))

        # purge expired
        purged = clear_entries(task=task.name, all=False, session=session)
        logger.debug('{} entries purged from backlog', purged)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputBacklog, 'backlog', builtin=True, api_ver=2)
