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

from sqlalchemy import Column, Integer, DateTime, Unicode, Boolean, or_, select, update, Index
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema, options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.utils.imdb import is_imdb_url, extract_id
from flexget.utils.sqlalchemy_utils import table_schema, table_add_column

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


class FilterSeen(object):
    """
        Remembers previously downloaded content and rejects them in
        subsequent executions. Without this plugin FlexGet would
        download all matching content on every execution.

        This plugin is enabled on all tasks by default.
        See wiki for more information.
    """
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'string', 'enum': ['global', 'local']}
        ]
    }

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['title', 'url', 'original_url']
        self.keyword = 'seen'

    @plugin.priority(255)
    def on_task_filter(self, task, config, remember_rejected=False):
        """Filter entries already accepted on previous runs."""
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

    def on_task_learn(self, task, config):
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
            if task.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))

    def learn(self, task, entry, fields=None, reason=None, local=False):
        """Marks entry as seen"""
        # no explicit fields given, use default
        if not fields:
            fields = self.fields
        se = SeenEntry(entry['title'], unicode(task.name), reason, local)
        remembered = []
        for field in fields:
            if field not in entry:
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
def db_cleanup(manager, session):
    log.debug('TODO: Disabled because of ticket #1321')
    return

    # Remove seen fields over a year old
    result = session.query(SeenField).filter(SeenField.added < datetime.now() - timedelta(days=365)).delete()
    if result:
        log.verbose('Removed %d seen fields older than 1 year.' % result)


def do_cli(manager, options):
    if options.seen_action == 'forget':
        seen_forget(manager, options)
    elif options.seen_action == 'add':
        seen_add(options)
    elif options.seen_action == 'search':
        seen_search(options)


def seen_forget(manager, options):
    forget_name = options.forget_value
    if is_imdb_url(forget_name):
        imdb_id = extract_id(forget_name)
        if imdb_id:
            forget_name = imdb_id

    count, fcount = forget(forget_name)
    console('Removed %s titles (%s fields)' % (count, fcount))
    manager.config_changed()


def seen_add(options):
    seen_name = options.add_value
    if is_imdb_url(seen_name):
        imdb_id = extract_id(seen_name)
        if imdb_id:
            seen_name = imdb_id

    with Session() as session:
        se = SeenEntry(seen_name, 'cli_seen')
        sf = SeenField('cli_seen', seen_name)
        se.fields.append(sf)
        session.add(se)
    console('Added %s as seen. This will affect all tasks.' % seen_name)


def seen_search(options):
    session = Session()
    try:
        search_term = '%' + options.search_term + '%'
        seen_entries = (session.query(SeenEntry).join(SeenField).
                        filter(SeenField.value.like(search_term)).order_by(SeenField.added).all())

        for se in seen_entries:
            console('ID: %s Name: %s Task: %s Added: %s' % (se.id, se.title, se.task, se.added.strftime('%c')))
            for sf in se.fields:
                console(' %s: %s' % (sf.field, sf.value))
            console('')

        if not seen_entries:
            console('No results')
    finally:
        session.close()


@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeen, 'seen', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('seen', do_cli, help='view or forget entries remembered by the seen plugin')
    subparsers = parser.add_subparsers(dest='seen_action', metavar='<action>')
    forget_parser = subparsers.add_parser('forget', help='forget entry or entire task from seen plugin database')
    forget_parser.add_argument('forget_value', metavar='<value>',
                               help='title or url of entry to forget, or name of task to forget')
    add_parser = subparsers.add_parser('add', help='add a title or url to the seen database')
    add_parser.add_argument('add_value', metavar='<value>', help='the title or url to add')
    search_parser = subparsers.add_parser('search', help='search text from the seen database')
    search_parser.add_argument('search_term', metavar='<search term>')
