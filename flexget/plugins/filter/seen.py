"""
Listens events:

forget (string)

    Given string can be task name, remembered field (url, imdb_url) or a title. If given value is a
    task name then everything in that task will be forgotten. With title all learned fields from it and the
    title will be forgotten. With field value only that particular field is forgotten.
"""

from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Unicode, Boolean, asc, or_, select, update, Index
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from flexget.manager import Session
from flexget.event import event
from flexget.plugin import register_plugin, priority, register_parser_option
from flexget import db_schema
from flexget.utils.sqlalchemy_utils import table_schema, table_add_column
from flexget.utils.imdb import is_imdb_url, extract_id

log = logging.getLogger('seen')
Base = db_schema.versioned_base('seen', 4)


@db_schema.upgrade('seen')
def upgrade(ver, session):
    if ver is None:
        log.info('Converting seen imdb_url to imdb_id for seen movies.')
        field_table = table_schema('seen_field', session)
        for row in session.execute(select([field_table.c.id, field_table.c.value], field_table.c.field == 'imdb_url')):
            new_values = {'field': 'imdb_id', 'value': extract_id(row['value'])}
            session.execute(update(field_table, field_table.c.id == row['id'], new_values))
        ver = 1
    if ver == 1:
        field_table = table_schema('seen_field', session)
        log.info('Adding index to seen_field table.')
        Index('ix_seen_field_seen_entry_id', field_table.c.seen_entry_id).create(bind=session.bind)
        ver = 2
    if ver == 2:
        log.info('Adding local column to seen_entry table')
        table_add_column('seen_entry', 'local', Boolean, session, default=False)
        ver = 3
    if ver == 3:
        # setting the default to False in the last migration was broken, fix the data
        log.info('Repairing seen table')
        entry_table = table_schema('seen_entry', session)
        session.execute(update(entry_table, entry_table.c.local == None, {'local': False}))
        ver = 4

    return ver


class SeenEntry(Base):

    __tablename__ = 'seen_entry'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    reason = Column(Unicode)
    task = Column('feed', Unicode)
    added = Column(DateTime)
    local = Column(Boolean)

    fields = relation('SeenField', backref='seen_entry', cascade='all, delete, delete-orphan')

    def __init__(self, title, task, reason=None, local=False):
        self.title = title
        self.reason = reason
        self.task = task
        self.added = datetime.now()
        self.local = local

    def __str__(self):
        return '<SeenEntry(title=%s,reason=%s,task=%s,added=%s)>' % (self.title, self.reason, self.task, self.added)


class SeenField(Base):

    __tablename__ = 'seen_field'

    id = Column(Integer, primary_key=True)
    seen_entry_id = Column(Integer, ForeignKey('seen_entry.id'), nullable=False, index=True)
    field = Column(Unicode)
    value = Column(Unicode, index=True)
    added = Column(DateTime)

    def __init__(self, field, value):
        self.field = field
        self.value = value
        self.added = datetime.now()

    def __str__(self):
        return '<SeenField(field=%s,value=%s,added=%s)>' % (self.field, self.value, self.added)


@event('forget')
def forget(value):
    """
    See module docstring
    :param string value: Can be task name, entry title or field value
    :return: count, field_count where count is number of entries removed and field_count number of fields
    """
    log.debug('forget called with %s' % value)
    session = Session()

    try:
        count = 0
        field_count = 0
        for se in session.query(SeenEntry).filter(or_(SeenEntry.title == value, SeenEntry.task == value)).all():
            field_count += len(se.fields)
            count += 1
            log.debug('forgetting %s' % se)
            session.delete(se)

        for sf in session.query(SeenField).filter(SeenField.value == value).all():
            se = session.query(SeenEntry).filter(SeenEntry.id == sf.seen_entry_id).first()
            field_count += len(se.fields)
            count += 1
            log.debug('forgetting %s' % se)
            session.delete(se)
        return count, field_count
    finally:
        session.commit()
        session.close()


class MigrateSeen(object):

    def migrate2(self):
        session = Session()

        try:
            from progressbar import ProgressBar, Percentage, Bar, ETA
        except:
            print 'Critical: progressbar library not found, try running `bin/easy_install progressbar` ?'
            return

        class Seen(Base):

            __tablename__ = 'seen'

            id = Column(Integer, primary_key=True)
            field = Column(String)
            value = Column(String, index=True)
            task = Column('feed', String)
            added = Column(DateTime)

            def __init__(self, field, value, task):
                self.field = field
                self.value = value
                self.task = task
                self.added = datetime.now()

            def __str__(self):
                return '<Seen(%s=%s)>' % (self.field, self.value)

        print ''

        # REPAIR / REMOVE DUPLICATES
        index = 0
        removed = 0
        total = session.query(Seen).count() + 1

        widgets = ['Repairing - ', ETA(), ' ', Percentage(), ' ', Bar(left='[', right=']')]
        bar = ProgressBar(widgets=widgets, maxval=total).start()

        for seen in session.query(Seen).all():
            index += 1
            if index % 10 == 0:
                bar.update(index)
            amount = 0
            for dupe in session.query(Seen).filter(Seen.value == seen.value):
                amount += 1
                if amount > 1:
                    removed += 1
                    session.delete(dupe)
        bar.finish()

        # MIGRATE
        total = session.query(Seen).count() + 1
        widgets = ['Upgrading - ', ETA(), ' ', Percentage(), ' ', Bar(left='[', right=']')]
        bar = ProgressBar(widgets=widgets, maxval=total).start()

        index = 0
        for seen in session.query(Seen).all():
            index += 1
            if not index % 10:
                bar.update(index)
            se = SeenEntry(u'N/A', seen.task, u'migrated')
            se.added = seen.added
            se.fields.append(SeenField(seen.field, seen.value))
            session.add(se)
        bar.finish()

        session.execute('drop table seen;')
        session.commit()

    def on_process_start(self, task):
        # migrate seen to seen_entry
        session = Session()
        from flexget.utils.sqlalchemy_utils import table_exists
        if table_exists('seen', session):
            self.migrate2()
        session.close()


class SeenSearch(object):

    def on_process_start(self, task):
        if not task.manager.options.seen_search:
            return

        task.manager.disable_tasks()

        session = Session()
        shown = []
        for field in session.query(SeenField).\
            filter(SeenField.value.like(unicode('%' + task.manager.options.seen_search + '%'))).\
                order_by(asc(SeenField.added)).all():

            se = session.query(SeenEntry).filter(SeenEntry.id == field.seen_entry_id).first()
            if not se:
                print 'ERROR: <SeenEntry(id=%s)> missing' % field.seen_entry_id
                continue

            # don't show duplicates
            if se.id in shown:
                continue
            shown.append(se.id)

            print 'ID: %s Name: %s Task: %s Added: %s' % (se.id, se.title, se.task, se.added.strftime('%c'))
            for sf in se.fields:
                print ' %s: %s' % (sf.field, sf.value)
            print ''

        if not shown:
            print 'No results'

        session.close()


class SeenForget(object):

    def on_process_start(self, task):
        if not task.manager.options.forget:
            return

        task.manager.disable_tasks()

        forget_name = task.manager.options.forget
        if is_imdb_url(forget_name):
            imdb_id = extract_id(forget_name)
            if imdb_id:
                forget_name = imdb_id

        count, fcount = forget(forget_name)
        log.info('Removed %s titles (%s fields)' % (count, fcount))
        task.manager.config_changed()


class SeenCmd(object):

    def on_process_start(self, task):
        if not task.manager.options.seen:
            return

        task.manager.disable_tasks()

        seen_name = task.manager.options.seen
        if is_imdb_url(seen_name):
            imdb_id = extract_id(seen_name)
            if imdb_id:
                seen_name = imdb_id

        session = Session()
        se = SeenEntry(u'--seen', unicode(task.name))
        sf = SeenField(u'--seen', seen_name)
        se.fields.append(sf)
        session.add(se)
        session.commit()

        log.info('Added %s as seen. This will affect all tasks.' % seen_name)


class FilterSeen(object):
    """
        Remembers previously downloaded content and rejects them in
        subsequent executions. Without this plugin FlexGet would
        download all matching content on every execution.

        This plugin is enabled on all tasks by default.
        See wiki for more information.
    """

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['title', 'url', 'original_url']
        self.keyword = 'seen'

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        root.accept('choice').accept_choices(['global', 'local'])
        return root

    @priority(255)
    def on_task_filter(self, task, config, remember_rejected=False):
        """Filter seen entries"""
        if config is False:
            log.debug('%s is disabled' % self.keyword)
            return

        fields = self.fields
        local = config == 'local'

        for entry in task.entries:
            # construct list of values looked
            values = []
            for field in fields:
                if field not in entry:
                    continue
                if entry[field] not in values and entry[field]:
                    values.append(unicode(entry[field]))
            if values:
                log.trace('querying for: %s' % ', '.join(values))
                # check if SeenField.value is any of the values
                found = task.session.query(SeenField).join(SeenEntry).filter(SeenField.value.in_(values))
                if local:
                    found = found.filter(SeenEntry.task == task.name)
                else:
                    found = found.filter(SeenEntry.local == False)
                found = found.first()
                if found:
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], found.value))
                    se = task.session.query(SeenEntry).filter(SeenEntry.id == found.seen_entry_id).one()
                    entry.reject('Entry with %s `%s` is already marked seen in the task %s at %s' % 
                                 (found.field, found.value, se.task, se.added.strftime('%Y-%m-%d %H:%M')),
                                remember=remember_rejected)

    def on_task_exit(self, task, config):
        """Remember succeeded entries"""
        if config is False:
            log.debug('disabled')
            return

        fields = self.fields
        if isinstance(config, list):
            fields.extend(config)

        for entry in task.accepted:
            self.learn(task, entry, fields=fields, local=config == 'local')
            # verbose if in learning mode
            if task.manager.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))

    def learn(self, task, entry, fields=None, reason=None, local=False):
        """Marks entry as seen"""
        # no explicit fields given, use default
        if not fields:
            fields = self.fields
        se = SeenEntry(entry['title'], unicode(task.name), reason, local)
        remembered = []
        for field in fields:
            if not field in entry:
                continue
            # removes duplicate values (eg. url, original_url are usually same)
            if entry[field] in remembered:
                continue
            remembered.append(entry[field])
            sf = SeenField(unicode(field), unicode(entry[field]))
            se.fields.append(sf)
            log.debug("Learned '%s' (field: %s)" % (entry[field], field))
        # Only add the entry to the session if it has one of the required fields
        if se.fields:
            task.session.add(se)

    def forget(self, task, title):
        """Forget SeenEntry with :title:. Return True if forgotten."""
        se = task.session.query(SeenEntry).filter(SeenEntry.title == title).first()
        if se:
            log.debug("Forgotten '%s' (%s fields)" % (title, len(se.fields)))
            task.session.delete(se)
            return True


@event('manager.db_cleanup')
def db_cleanup(session):
    log.debug('TODO: Disabled because of ticket #1321')
    return

    # Remove seen fields over a year old
    result = session.query(SeenField).filter(SeenField.added < datetime.now() - timedelta(days=365)).delete()
    if result:
        log.verbose('Removed %d seen fields older than 1 year.' % result)


register_plugin(FilterSeen, 'seen', builtin=True, api_ver=2)
register_plugin(SeenSearch, '--seen-search', builtin=True)
register_plugin(SeenCmd, '--seen', builtin=True)
register_plugin(SeenForget, '--forget', builtin=True)
register_plugin(MigrateSeen, 'migrate_seen', builtin=True)

register_parser_option('--forget', action='store', dest='forget', default=False,
                       metavar='TASK|VALUE', help='Forget task (completely) or given title or url.')
register_parser_option('--seen', action='store', dest='seen', default=False,
                       metavar='VALUE', help='Add title or url to what has been seen in tasks.')
register_parser_option('--seen-search', action='store', dest='seen_search', default=False,
                       metavar='VALUE', help='Search given text from seen database.')
