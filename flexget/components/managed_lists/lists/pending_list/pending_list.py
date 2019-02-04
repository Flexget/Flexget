from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from collections import MutableSet

from sqlalchemy import or_
from sqlalchemy.sql.elements import and_

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from . import db

plugin_name = 'pending_list'
log = logging.getLogger(plugin_name)


class PendingListSet(MutableSet):
    def _db_list(self, session):
        return (
            session.query(db.PendingListList)
            .filter(db.PendingListList.name == self.config)
            .first()
        )

    def __init__(self, config):
        self.config = config
        with Session() as session:
            if not self._db_list(session):
                session.add(db.PendingListList(name=self.config))

    def _entry_query(self, session, entry, approved=None):
        query = (
            session.query(db.PendingListEntry)
            .filter(db.PendingListEntry.list_id == self._db_list(session).id)
            .filter(
                or_(
                    db.PendingListEntry.title == entry['title'],
                    and_(
                        db.PendingListEntry.original_url,
                        db.PendingListEntry.original_url == entry['original_url'],
                    ),
                )
            )
        )
        if approved:
            query = query.filter(db.PendingListEntry.approved == True)
        return query.first()

    def __iter__(self):
        with Session() as session:
            for e in (
                self._db_list(session)
                .entries.filter(db.PendingListEntry.approved == True)
                .order_by(db.PendingListEntry.added.desc())
                .all()
            ):
                log.debug('returning %s', e.entry)
                yield e.entry

    def __contains__(self, entry):
        with Session() as session:
            return self._entry_query(session, entry) is not None

    def __len__(self):
        with Session() as session:
            return self._db_list(session).entries.count()

    def discard(self, entry):
        with Session() as session:
            db_entry = self._entry_query(session=session, entry=entry)
            if db_entry:
                log.debug('deleting entry %s', db_entry)
                session.delete(db_entry)

    def add(self, entry):
        # Evaluate all lazy fields so that no db access occurs during our db session
        entry.values()

        with Session() as session:
            stored_entry = self._entry_query(session, entry)
            if stored_entry:
                # Refresh all the fields if we already have this entry
                log.debug('refreshing entry %s', entry)
                stored_entry.entry = entry
            else:
                log.debug('adding entry %s to list %s', entry, self._db_list(session).name)
                stored_entry = db.PendingListEntry(
                    entry=entry, pending_list_id=self._db_list(session).id
                )
            session.add(stored_entry)

    def __ior__(self, other):
        # Optimization to only open one session when adding multiple items
        # Make sure lazy lookups are done before opening our session to prevent db locks
        for value in other:
            value.values()
        for value in other:
            self.add(value)
        return self

    @property
    def immutable(self):
        return False

    def _from_iterable(self, it):
        return set(it)

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    def get(self, entry):
        with Session() as session:
            match = self._entry_query(session=session, entry=entry, approved=True)
            return Entry(match.entry) if match else None


class PendingList(object):
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return PendingListSet(config)

    def on_task_input(self, task, config):
        return list(PendingListSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PendingList, plugin_name, api_ver=2, interfaces=['task', 'list'])
