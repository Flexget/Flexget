"""
    Listens events:

    forget (string)

        Given string can be feed name, remembered field (url, imdb_url) or a title. If given value is a
        feed name then everything in that feed will be forgotten. With title all learned fields from it and the
        title will be forgotten. With field value only that particular field is forgotten.

"""

import logging
from flexget.event import event
from flexget.manager import Base
from flexget.plugin import register_plugin, priority, register_parser_option
from sqlalchemy import Column, Integer, String, DateTime, Unicode, asc, or_
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from datetime import datetime
from flexget.manager import Session

log = logging.getLogger('seen')


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
    seen_entry_id = Column(Integer, ForeignKey('seen_entry.id'), nullable=False)
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

    def migrate(self, feed):
        """Migrates 0.9 session data into new database"""

        session = Session()
        try:
            shelve = feed.manager.shelve_session
            count = 0
            log.info('If this crashes, you can\'t migrate 0.9 data to 1.0 ... sorry')
            for name, data in shelve.iteritems():
                if not 'seen' in data:
                    continue
                seen = data['seen']
                for k, v in seen.iteritems():
                    se = SeenEntry(u'N/A', seen.feed, u'migrated')
                    se.fields.append(SeenField(u'unknown', k))
                    session.add(se)
                    count += 1
            session.commit()
            log.info('It worked! Migrated %s seen items' % count)
        except Exception:
            log.critical('It crashed :(')
        finally:
            session.close()

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
            if (index % 10 == 0):
                bar.update(index)
            se = SeenEntry(u'N/A', seen.feed, u'migrated')
            se.added = seen.added
            se.fields.append(SeenField(seen.field, seen.value))
            session.add(se)
        bar.finish()

        session.execute('drop table seen;')
        session.commit()

    def on_process_start(self, feed):
        # migrate shelve -> sqlalchemy
        if feed.manager.shelve_session:
            self.migrate(feed)

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
        count, fcount = forget(unicode(feed.manager.options.forget))
        log.info('Removed %s titles (%s fields)' % (count, fcount))


class SeenCmd(object):

    def on_process_start(self, feed):
        if not feed.manager.options.seen:
            return

        feed.manager.disable_feeds()

        session = Session()
        se = SeenEntry(u'--seen', unicode(feed.name))
        sf = SeenField(u'--seen', unicode(feed.manager.options.seen))
        se.fields.append(sf)
        session.add(se)
        session.commit()

        log.info('Added %s as seen. This will affect all feeds.' % feed.manager.options.seen)


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
                if entry[field] not in values and entry[field] != '':
                    values.append(entry[field])
            if values:
                log.debugall('querying for: %s' % ', '.join(values))
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
