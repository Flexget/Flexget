import hashlib
import logging
from sqlalchemy import Column, Integer, String, Unicode, ForeignKey
from sqlalchemy.orm import relation, eagerload
from flexget.manager import Base
from flexget.plugin import register_plugin, register_parser_option, priority, get_plugin_by_name, PluginDependencyError

log = logging.getLogger('only_new')


class OnlyNewFeed(Base):

    __tablename__ = 'onlynew_feed'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    hash = Column(String)

    entries = relation('OnlyNewEntry', backref='feed', cascade='all, delete, delete-orphan')


class OnlyNewEntry(Base):

    __tablename__ = 'onlynew_entry'

    id = Column(Integer, primary_key=True)
    uid = Column(String)

    feed_id = Column(Integer, ForeignKey('onlynew_feed.id'), nullable=False)


class FilterOnlyNew(object):
    """Causes input plugins to only emit entries that haven't been seen on previous runs."""

    def validator(self):
        from flexget.validator import BooleanValidator
        return BooleanValidator()

    # Run after inputs at default priority have created their entries
    @priority(120)
    def on_feed_input(self, feed):
        if not feed.config.get('only_new', True):
            return
        # Generate hash for current config
        config_hash = hashlib.md5(str(feed.config.items())).hexdigest()
        # See if the feed has the same hash as last run
        old_feed = feed.session.query(OnlyNewFeed).filter(OnlyNewFeed.name == feed.name).first()
        if not old_feed:
            log.debug('No history for this feed.')
        elif old_feed.hash != config_hash:
            log.debug('Config has changed since last run, not rejecting anything.')
        elif not feed.manager.options.no_only_new:
            # Config hasn't changed, reject all the entries we saw last run
            seen_uids = [entry.uid for entry in old_feed.entries]
            for entry in feed.entries:
                if entry['uid'] in seen_uids:
                    feed.reject(entry, 'Entry was processed on previous run.')
            # Make sure details plugin doesn't complain when there are no entries
            try:
                details = get_plugin_by_name('details').instance
                if feed.name not in details.no_entries_ok:
                    log.debug('appending %s to details plugin no_entries_ok' % feed.name)
                    details.no_entries_ok.append(feed.name)
            except PluginDependencyError:
                log.debug('unable to get details plugin')

        if old_feed:
            # We will reuse this object to write the new entries
            new_feed = old_feed
            new_feed.hash = config_hash
        else:
            new_feed = OnlyNewFeed(name=feed.name, hash=config_hash)
        new_feed.entries = [OnlyNewEntry(uid=entry['uid']) for entry in feed.entries]

        # Clear our history for this feed from the db
        feed.session.query(OnlyNewFeed).filter(OnlyNewFeed.name == feed.name).delete()
        feed.session.flush()
        # Write the new info to the db
        feed.session.merge(new_feed)

    def on_entry_fail(self, feed, entry, **kwargs):
        if not feed.config.get('only_new', True):
            return
        # Remove failed entry from the only_new database so that it can be retried next run
        db_entry = feed.session.query(OnlyNewEntry).join(OnlyNewFeed).filter(OnlyNewFeed.name == feed.name).\
            filter(OnlyNewEntry.uid == entry['uid']).first()
        if db_entry:
            feed.session.delete(db_entry)


register_plugin(FilterOnlyNew, 'only_new')
register_parser_option('--no-only-new', action='store_true', dest='no_only_new', default=0,
                       help='Disable only_new plugin filtering for this run.')
