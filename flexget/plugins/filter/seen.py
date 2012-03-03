"""
Listens events:

forget (string)

    Given string can be feed name, remembered field (url, imdb_url) or a title. If given value is a
    feed name then everything in that feed will be forgotten. With title all learned fields from it and the
    title will be forgotten. With field value only that particular field is forgotten.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Unicode, asc, or_, select, update, Index
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from flexget.manager import Session
from flexget.event import event
from flexget.plugin import register_plugin, priority, register_parser_option
from flexget import schema
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.imdb import is_imdb_url, extract_id

log = logging.getLogger('seen')
Base = schema.versioned_base('seen', 2)


@schema.upgrade('seen')
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
    return ver


class SeenEntry(Base):

    __tablename__ = 'seen_entry'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    reason = Column(Unicode)
    feed = Column(Unicode)
    added = Column(DateTime)

    fields = relation('SeenField', backref='seen_entry', cascade='all, delete, delete-orphan')

    def __init__(self, title, feed, reason=None):
        self.title = title
        self.reason = reason
        self.feed = feed
        self.added = datetime.now()

    def __str__(self):
        return '<SeenEntry(title=%s,reason=%s,feed=%s,added=%s)>' % (self.title, self.reason, self.feed, self.added)


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
    :param string value: Can be feed name, entry title or field value
    :return: count, field_count where count is number of entries removed and field_count number of fields
    """
    log.debug('forget called with %s' % value)
    session = Session()

    try:
        count = 0
        field_count = 0
        for se in session.query(SeenEntry).filter(or_(SeenEntry.title == value, SeenEntry.feed == value)).all():
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
            feed = Column(String)
            added = Column(DateTime)

            def __init__(self, field, value, feed):
                self.field = field
                self.value = value
                self.feed = feed
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
            se = SeenEntry(u'N/A', seen.feed, u'migrated')
            se.added = seen.added
            se.fields.append(SeenField(seen.field, seen.value))
            session.add(se)
        bar.finish()

        session.execute('drop table seen;')
        session.commit()

    def on_process_start(self, feed):
        # migrate seen to seen_entry
        session = Session()
        from flexget.utils.sqlalchemy_utils import table_exists
        if table_exists('seen', session):
            self.migrate2()
        session.close()


class SeenSearch(object):

    def on_process_start(self, feed):
        if not feed.manager.options.seen_search:
            return

        feed.manager.disable_feeds()

        session = Session()
        shown = []
        for field in session.query(SeenField).\
            filter(SeenField.value.like(unicode('%' + feed.manager.options.seen_search + '%'))).\
            order_by(asc(SeenField.added)).all():

            se = session.query(SeenEntry).filter(SeenEntry.id == field.seen_entry_id).first()
            if not se:
                print 'ERROR: <SeenEntry(id=%s)> missing' % field.seen_entry_id
                continue

            # don't show duplicates
            if se.id in shown:
                continue
            shown.append(se.id)

            print 'ID: %s Name: %s Feed: %s Added: %s' % (se.id, se.title, se.feed, se.added.strftime('%c'))
            for sf in se.fields:
                print ' %s: %s' % (sf.field, sf.value)
            print ''

        if not shown:
            print 'No results'

        session.close()


class SeenForget(object):

    def on_process_start(self, feed):
        if not feed.manager.options.forget:
            return

        feed.manager.disable_feeds()

        forget_name = unicode(feed.manager.options.forget)
        if is_imdb_url(forget_name):
            imdb_id = extract_id(forget_name)
            if imdb_id:
                forget_name = imdb_id

        count, fcount = forget(forget_name)
        log.info('Removed %s titles (%s fields)' % (count, fcount))


class SeenCmd(object):

    def on_process_start(self, feed):
        if not feed.manager.options.seen:
            return

        feed.manager.disable_feeds()

        seen_name = unicode(feed.manager.options.seen)
        if is_imdb_url(seen_name):
            imdb_id = extract_id(seen_name)
            if imdb_id:
                seen_name = imdb_id

        session = Session()
        se = SeenEntry(u'--seen', unicode(feed.name))
        sf = SeenField(u'--seen', seen_name)
        se.fields.append(sf)
        session.add(se)
        session.commit()

        log.info('Added %s as seen. This will affect all feeds.' % seen_name)


class FilterSeen(object):
    """
        Remembers previously downloaded content and rejects them in
        subsequent executions. Without this plugin FlexGet would
        download all matching content on every execution.

        This plugin is enabled on all feeds by default.
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
        root.accept('list').accept('text')
        return root

    @priority(255)
    def on_feed_filter(self, feed, config, remember_rejected=False):
        """Filter seen entries"""
        if config is False:
            log.debug('%s is disabled' % self.keyword)
            return

        fields = self.fields
        if isinstance(config, list):
            fields.extend(config)

        for entry in feed.entries:
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
                found = feed.session.query(SeenField).filter(SeenField.value.in_(values)).first()
                if found:
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], found.value))
                    feed.reject(entry, 'Entry with %s `%s` is already seen' % (found.field, found.value),
                                remember=remember_rejected)

    def on_feed_exit(self, feed, config):
        """Remember succeeded entries"""
        if config is False:
            log.debug('disabled')
            return

        fields = self.fields
        if isinstance(config, list):
            fields.extend(config)

        for entry in feed.accepted:
            self.learn(feed, entry, fields=fields)
            # verbose if in learning mode
            if feed.manager.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))

    def learn(self, feed, entry, fields=None, reason=None):
        """Marks entry as seen"""
        # no explicit fields given, use default
        if not fields:
            fields = self.fields
        se = SeenEntry(entry['title'], unicode(feed.name), reason)
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
            feed.session.add(se)

    def forget(self, feed, title):
        """Forget SeenEntry with :title:. Return True if forgotten."""
        se = feed.session.query(SeenEntry).filter(SeenEntry.title == title).first()
        if se:
            log.debug("Forgotten '%s' (%s fields)" % (title, len(se.fields)))
            feed.session.delete(se)
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
                       metavar='FEED|VALUE', help='Forget feed (completely) or given title or url.')
register_parser_option('--seen', action='store', dest='seen', default=False,
                       metavar='VALUE', help='Add title or url to what has been seen in feeds.')
register_parser_option('--seen-search', action='store', dest='seen_search', default=False,
                       metavar='VALUE', help='Search given text from seen database.')
