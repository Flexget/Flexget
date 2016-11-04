"""
Listens events:

forget (string)

    Given string can be task name, remembered field (url, imdb_url) or a title. If given value is a
    task name then everything in that task will be forgotten. With title all learned fields from it and the
    title will be forgotten. With field value only that particular field is forgotten.
"""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, Unicode, Boolean, or_, select, update, Index
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import with_session
from flexget.utils.imdb import extract_id
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

    def __init__(self, title, task, reason=None, local=None):
        if local is None:
            local = False
        self.title = title
        self.reason = reason
        self.task = task
        self.added = datetime.now()
        self.local = local

    def __str__(self):
        return '<SeenEntry(title=%s,reason=%s,task=%s,added=%s)>' % (self.title, self.reason, self.task, self.added)

    def to_dict(self):
        fields = []
        for field in self.fields:
            fields.append(field.to_dict())

        seen_entry_object = {
            'id': self.id,
            'title': self.title,
            'reason': self.reason,
            'task': self.task,
            'added': self.added,
            'local': self.local,
            'fields': fields
        }
        return seen_entry_object


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

    def to_dict(self):
        return {
            'field_name': self.field,
            'field_id': self.id,
            'value': self.value,
            'added': self.added,
            'seen_entry_id': self.seen_entry_id
        }


@with_session
def add(title, task_name, fields, reason=None, local=None, session=None):
    """
    Adds seen entries to DB

    :param title: name of title to be added
    :param task_name: name of task to be added
    :param fields: Dict of fields to be added to seen object
    :return: Seen Entry object as committed to DB
    """
    se = SeenEntry(title, task_name, reason, local)
    for field, value in list(fields.items()):
        sf = SeenField(field, value)
        se.fields.append(sf)
    session.add(se)
    session.commit()
    return se.to_dict()


@event('forget')
def forget(value):
    """
    See module docstring
    :param string value: Can be task name, entry title or field value
    :return: count, field_count where count is number of entries removed and field_count number of fields
    """
    with Session() as session:
        log.debug('forget called with %s', value)
        count = 0
        field_count = 0
        for se in session.query(SeenEntry).filter(or_(SeenEntry.title == value, SeenEntry.task == value)).all():
            field_count += len(se.fields)
            count += 1
            log.debug('forgetting %s', se)
            session.delete(se)

        for sf in session.query(SeenField).filter(SeenField.value == value).all():
            se = session.query(SeenEntry).filter(SeenEntry.id == sf.seen_entry_id).first()
            field_count += len(se.fields)
            count += 1
            log.debug('forgetting %s', se)
            session.delete(se)
    return count, field_count


@with_session
def search_by_field_values(field_value_list, task_name, local=False, session=None):
    """
    Return a SeenEntry instance if it matches field values
    :param field_value_list: List of field values to match
    :param task_name: Name of task to compare to in case local flag is sent
    :param local: Local flag
    :param session: Current session
    :return: SeenEntry Object or None
    """
    found = session.query(SeenField).join(SeenEntry).filter(SeenField.value.in_(field_value_list))
    if local:
        found = found.filter(SeenEntry.task == task_name)
    else:
        # Entries added from CLI were having local marked as None rather than False for a while gh#879
        found = found.filter(or_(SeenEntry.local == False, SeenEntry.local == None))
    return found.first()


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
            {'type': 'string', 'enum': ['global', 'local']},
            {'type': 'object',
             'properties': {
                 'local': {'type': 'boolean'},
                 'fields': {'type': 'array',
                            'items': {'type': 'string'},
                            "minItems": 1,
                            "uniqueItems": True}
             }}
        ]
    }

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['title', 'url', 'original_url']
        self.keyword = 'seen'

    def prepare_config(self, config):
        if config is None:
            config = {}
        elif isinstance(config, bool):
            if config is False:
                return config
            else:
                config = {'local': False}
        elif isinstance(config, basestring):
            config = {'local': config == 'local'}

        config.setdefault('local', False)
        config.setdefault('fields', self.fields)
        return config

    @plugin.priority(255)
    def on_task_filter(self, task, config, remember_rejected=False):
        """Filter entries already accepted on previous runs."""
        config = self.prepare_config(config)
        if config is False:
            log.debug('%s is disabled' % self.keyword)
            return

        fields = config.get('fields')
        local = config.get('local')

        for entry in task.entries:
            # construct list of values looked
            values = []
            for field in fields:
                if field not in entry:
                    continue
                if entry[field] not in values and entry[field]:
                    values.append(str(entry[field]))
            if values:
                log.trace('querying for: %s' % ', '.join(values))
                # check if SeenField.value is any of the values
                found = search_by_field_values(field_value_list=values, task_name=task.name, local=local,
                                               session=task.session)
                if found:
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], found.value))
                    se = task.session.query(SeenEntry).filter(SeenEntry.id == found.seen_entry_id).one()
                    entry.reject('Entry with %s `%s` is already marked seen in the task %s at %s' %
                                 (found.field, found.value, se.task, se.added.strftime('%Y-%m-%d %H:%M')),
                                 remember=remember_rejected)

    def on_task_learn(self, task, config):
        """Remember succeeded entries"""
        config = self.prepare_config(config)
        if config is False:
            log.debug('disabled')
            return

        fields = config.get('fields')
        local = config.get('local')

        if isinstance(config, list):
            fields.extend(config)

        for entry in task.accepted:
            self.learn(task, entry, fields=fields, local=local)
            # verbose if in learning mode
            if task.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))

    def learn(self, task, entry, fields=None, reason=None, local=False):
        """Marks entry as seen"""
        # no explicit fields given, use default
        if not fields:
            fields = self.fields
        se = SeenEntry(entry['title'], str(task.name), reason, local)
        remembered = []
        for field in fields:
            if field not in entry:
                continue
            # removes duplicate values (eg. url, original_url are usually same)
            if entry[field] in remembered:
                continue
            remembered.append(entry[field])
            sf = SeenField(str(field), str(entry[field]))
            se.fields.append(sf)
            log.debug("Learned '%s' (field: %s, local: %d)" % (entry[field], field, local))
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
    # TODO: Look into this, is it still valid?
    log.debug('TODO: Disabled because of ticket #1321')
    return

    # Remove seen fields over a year old
    # result = session.query(SeenField).filter(SeenField.added < datetime.now() - timedelta(days=365)).delete()
    # if result:
    #    log.verbose('Removed %d seen fields older than 1 year.' % result)


@with_session
def search(count=None, value=None, status=None, start=None, stop=None, order_by='added', descending=False,
           session=None):
    query = session.query(SeenEntry).join(SeenField)
    if value:
        query = query.filter(SeenField.value.like(value))
    if status is not None:
        query = query.filter(SeenEntry.local == status)
    if count:
        return query.group_by(SeenEntry).count()
    if descending:
        query = query.order_by(getattr(SeenEntry, order_by).desc())
    else:
        query = query.order_by(getattr(SeenEntry, order_by))
    return query.group_by(SeenEntry).slice(start, stop).from_self()


@with_session
def get_entry_by_id(entry_id, session=None):
    return session.query(SeenEntry).filter(SeenEntry.id == entry_id).one()


@with_session
def forget_by_id(entry_id, session=None):
    """
    Delete SeenEntry via its ID
    :param entry_id: SeenEntry ID
    :param session: DB Session
    """
    entry = get_entry_by_id(entry_id, session=session)
    log.debug('Deleting seen entry with ID {0}'.format(entry_id))
    session.delete(entry)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeen, 'seen', builtin=True, api_ver=2)
