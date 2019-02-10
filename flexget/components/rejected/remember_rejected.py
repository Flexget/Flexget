from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta

from past.builtins import basestring
from sqlalchemy import and_

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import parse_timedelta

from . import db

log = logging.getLogger('remember_rej')


class FilterRememberRejected(object):
    """Internal.
    Rejects entries which have been rejected in the past.

    This is enabled when item is rejected with remember=True flag.

    Example::
        entry.reject('message', remember=True)
    """

    @plugin.priority(0)
    def on_task_start(self, task, config):
        """Purge remembered entries if the config has changed."""
        with Session() as session:
            # See if the task has changed since last run
            old_task = (
                session.query(db.RememberTask).filter(db.RememberTask.name == task.name).first()
            )
            if not task.is_rerun and old_task and task.config_modified:
                log.debug('Task config has changed since last run, purging remembered entries.')
                session.delete(old_task)
                old_task = None
            if not old_task:
                # Create this task in the db if not present
                session.add(db.RememberTask(name=task.name))
            elif not task.is_rerun:
                # Delete expired items if this is not a rerun
                deleted = (
                    session.query(db.RememberEntry)
                    .filter(db.RememberEntry.task_id == old_task.id)
                    .filter(db.RememberEntry.expires < datetime.now())
                    .delete()
                )
                if deleted:
                    log.debug('%s entries have expired from remember_rejected table.' % deleted)
                    task.config_changed()

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_input(self, task, config):
        for entry in task.all_entries:
            entry.on_reject(self.on_entry_reject)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        """Reject any remembered entries from previous runs"""
        with Session() as session:
            (task_id,) = (
                session.query(db.RememberTask.id).filter(db.RememberTask.name == task.name).first()
            )
            reject_entries = session.query(db.RememberEntry).filter(
                db.RememberEntry.task_id == task_id
            )
            if reject_entries.count():
                # Reject all the remembered entries
                for entry in task.entries:
                    if not entry.get('url'):
                        # We don't record or reject any entries without url
                        continue
                    reject_entry = reject_entries.filter(
                        and_(
                            db.RememberEntry.title == entry['title'],
                            db.RememberEntry.url == entry['original_url'],
                        )
                    ).first()
                    if reject_entry:
                        entry.reject(
                            'Rejected on behalf of %s plugin: %s'
                            % (reject_entry.rejected_by, reject_entry.reason)
                        )

    def on_entry_reject(self, entry, remember=None, remember_time=None, **kwargs):
        # We only remember rejections that specify the remember keyword argument
        if not (remember or remember_time):
            return
        if not entry.get('title') or not entry.get('original_url'):
            log.debug('Can\'t remember rejection for entry without title or url.')
            return
        if remember_time:
            if isinstance(remember_time, basestring):
                remember_time = parse_timedelta(remember_time)
        message = 'Remembering rejection of `%s`' % entry['title']
        if remember_time:
            message += ' for %i minutes' % (remember_time.seconds / 60)
        log.info(message)
        entry['remember_rejected'] = remember_time or remember

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_learn(self, task, config):
        with Session() as session:
            for entry in task.all_entries:
                if not entry.get('remember_rejected'):
                    continue
                expires = None
                if isinstance(entry['remember_rejected'], timedelta):
                    expires = datetime.now() + entry['remember_rejected']

                (remember_task_id,) = (
                    session.query(db.RememberTask.id)
                    .filter(db.RememberTask.name == task.name)
                    .first()
                )
                session.add(
                    db.RememberEntry(
                        title=entry['title'],
                        url=entry['original_url'],
                        task_id=remember_task_id,
                        rejected_by=entry.get('rejected_by'),
                        reason=entry.get('reason'),
                        expires=expires,
                    )
                )


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRememberRejected, 'remember_rejected', builtin=True, api_ver=2)
