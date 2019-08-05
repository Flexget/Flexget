from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from . import db

log = logging.getLogger('pending_approval')


class PendingApproval(object):
    schema = {
        'type': 'boolean',
        'deprecated': 'pending_approval is deprecated, switch to using pending_list',
    }

    @staticmethod
    def _item_query(entry, task, session):
        return (
            session.query(db.PendingEntry)
            .filter(db.PendingEntry.task_name == task.name)
            .filter(db.PendingEntry.title == entry['title'])
            .filter(db.PendingEntry.url == entry['url'])
            .first()
        )

    def on_task_input(self, task, config):
        if not config:
            return

        approved_entries = []
        with Session() as session:
            for approved_entry in (
                session.query(db.PendingEntry)
                .filter(db.PendingEntry.task_name == task.name)
                .filter(db.PendingEntry.approved == True)
                .all()
            ):
                e = approved_entry.entry
                e['approved'] = True
                e['immortal'] = True
                approved_entries.append(e)

        return approved_entries

    # Run after all other filters
    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_filter(self, task, config):
        if not config:
            return

        with Session() as session:
            for entry in task.entries:
                # Cache all new task entries
                if entry.get('approved'):
                    entry.accept('entry is marked as approved')
                elif not self._item_query(entry, task, session):
                    log.verbose('creating new pending entry %s', entry)
                    session.add(db.PendingEntry(task_name=task.name, entry=entry))
                    entry.reject('new unapproved entry, caching and waiting for approval')

    def on_task_learn(self, task, config):
        if not config:
            return
        with Session() as session:
            # Delete all accepted entries that have passed the pending phase
            for entry in task.accepted:
                if entry.get('approved'):
                    db_entry = self._item_query(entry, task, session)
                    if db_entry and db_entry.approved:
                        log.debug('deleting approved entry %s', db_entry)
                        session.delete(db_entry)


@event('plugin.register')
def register_plugin():
    plugin.register(PendingApproval, 'pending_approval', api_ver=2)
