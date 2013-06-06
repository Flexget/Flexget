from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Unicode, DateTime, ForeignKey, and_, Index
from sqlalchemy.orm import relation
from flexget import db_schema
from flexget.event import event
from flexget.plugin import register_plugin, register_parser_option, priority
from flexget.utils.sqlalchemy_utils import table_columns, drop_tables, table_add_column
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('remember_rej')
Base = db_schema.versioned_base('remember_rejected', 3)


@db_schema.upgrade('remember_rejected')
def upgrade(ver, session):
    if ver is None:
        columns = table_columns('remember_rejected_entry', session)
        if 'uid' in columns:
            # Drop the old table
            log.info('Dropping old version of remember_rejected_entry table from db')
            drop_tables(['remember_rejected_entry'], session)
            # Create new table from the current model
            Base.metadata.create_all(bind=session.bind)
            # We go directly to version 2, as remember_rejected_entries table has just been made from current model
            # TODO: Fix this somehow. Just avoid dropping tables?
            ver = 3
        else:
            ver = 0
    if ver == 0:
        log.info('Adding reason column to remember_rejected_entry table.')
        table_add_column('remember_rejected_entry', 'reason', String, session)
        ver = 1
    if ver == 1:
        log.info('Adding `added` column to remember_rejected_entry table.')
        table_add_column('remember_rejected_entry', 'added', DateTime, session, default=datetime.now)
        ver = 2
    if ver == 2:
        log.info('Adding expires column to remember_rejected_entry table.')
        table_add_column('remember_rejected_entry', 'expires', DateTime, session)
        ver = 3
    return ver


class RememberTask(Base):

    __tablename__ = 'remember_rejected_feeds'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    entries = relation('RememberEntry', backref='task', cascade='all, delete, delete-orphan')


class RememberEntry(Base):

    __tablename__ = 'remember_rejected_entry'

    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    expires = Column(DateTime)
    title = Column(Unicode)
    url = Column(String)
    rejected_by = Column(String)
    reason = Column(String)

    task_id = Column('feed_id', Integer, ForeignKey('remember_rejected_feeds.id'), nullable=False)

Index('remember_feed_title_url', RememberEntry.task_id, RememberEntry.title, RememberEntry.url)


class FilterRememberRejected(object):
    """Internal.
    Rejects entries which have been rejected in the past.

    This is enabled when item is rejected with remember=True flag.

    Example::
        entry.reject('message', remember=True)
    """

    @priority(0)
    def on_task_start(self, task, config):
        """Purge remembered entries if the config has changed."""
        # See if the task has changed since last run
        old_task = task.session.query(RememberTask).filter(RememberTask.name == task.name).first()
        if not task.is_rerun and old_task and (task.config_modified or task.manager.options.forget_rejected):
            if task.manager.options.forget_rejected:
                log.info('Forgetting previous rejections.')
                task.config_changed()
            else:
                log.debug('Task config has changed since last run, purging remembered entries.')
            task.session.delete(old_task)
            old_task = None
        if not old_task:
            # Create this task in the db if not present
            task.session.add(RememberTask(name=task.name))
        elif not task.is_rerun:
            # Delete expired items if this is not a rerun
            deleted = task.session.query(RememberEntry).filter(RememberEntry.task_id == old_task.id).\
                filter(RememberEntry.expires < datetime.now()).delete()
            if deleted:
                log.debug('%s entries have expired from remember_rejected table.' % deleted)
                task.config_changed()
        task.session.commit()

    @priority(-255)
    def on_task_input(self, task, config):
        for entry in task.all_entries:
            entry.on_reject(self.on_entry_reject, task=task)

    @priority(255)
    def on_task_filter(self, task, config):
        """Reject any remembered entries from previous runs"""
        (task_id,) = task.session.query(RememberTask.id).filter(RememberTask.name == task.name).first()
        reject_entries = task.session.query(RememberEntry).filter(RememberEntry.task_id == task_id)
        if reject_entries.count():
            # Reject all the remembered entries
            for entry in task.entries:
                if not entry.get('url'):
                    # We don't record or reject any entries without url
                    continue
                reject_entry = reject_entries.filter(and_(RememberEntry.title == entry['title'],
                                                          RememberEntry.url == entry['original_url'])).first()
                if reject_entry:
                    entry.reject('Rejected on behalf of %s plugin: %s' %
                        (reject_entry.rejected_by, reject_entry.reason))

    def on_entry_reject(self, entry, task=None, remember=None, remember_time=None, **kwargs):
        # We only remember rejections that specify the remember keyword argument
        if not remember and not remember_time:
            return
        expires = None
        if remember_time:
            if isinstance(remember_time, basestring):
                remember_time = parse_timedelta(remember_time)
            expires = datetime.now() + remember_time
        if not entry.get('title') or not entry.get('original_url'):
            log.debug('Can\'t remember rejection for entry without title or url.')
            return
        message = 'Remembering rejection of `%s`' % entry['title']
        if remember_time:
            message += ' for %i minutes' % (remember_time.seconds / 60)
        log.info(message)
        (remember_task_id,) = task.session.query(RememberTask.id).filter(RememberTask.name == task.name).first()
        task.session.add(RememberEntry(title=entry['title'], url=entry['original_url'], task_id=remember_task_id,
                                       rejected_by=task.current_plugin, reason=kwargs.get('reason'), expires=expires))
        # The test stops passing when this is taken out for some reason...
        task.session.flush()


@event('manager.db_cleanup')
def db_cleanup(session):
    # Remove entries older than 30 days
    result = session.query(RememberEntry).filter(RememberEntry.added < datetime.now() - timedelta(days=30)).delete()
    if result:
        log.verbose('Removed %d entries from remember rejected table.' % result)


register_plugin(FilterRememberRejected, 'remember_rejected', builtin=True, api_ver=2)
register_parser_option('--forget-rejected', action='store_true', dest='forget_rejected',
                       help='Forget all previous rejections so entries can be processed again.')
