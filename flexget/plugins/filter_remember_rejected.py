import hashlib
import logging
from sqlalchemy import Column, Integer, String, Unicode, ForeignKey
from sqlalchemy.orm import relation
from flexget.manager import Base
from flexget.plugin import register_plugin, priority

log = logging.getLogger('remember_rejected')


class RememberFeed(Base):

    __tablename__ = 'remember_rejected_feeds'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    hash = Column(String)

    entries = relation('RememberEntry', backref='feed', cascade='all, delete, delete-orphan')


class RememberEntry(Base):

    __tablename__ = 'remember_rejected_entry'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String)
    rejected_by = Column(Unicode)

    feed_id = Column(Integer, ForeignKey('remember_rejected_feeds.id'), nullable=False)


class FilterRememberRejected(object):
    """Internal.
    Rejects entries which have been rejected in the past.

    This is enabled when item is rejected with remember=True flag.

    Example:
        feed.reject(entry, 'message', remember=True)
    """

    # This runs at the beginning of metainfo phase to avoid re-parsing metainfo for entries that will be rejected
    @priority(255)
    def on_feed_metainfo(self, feed):
        """Purge remembered entries if the config has changed and write new hash"""

        # Generate hash for current config
        config_hash = hashlib.md5(str(feed.config.items())).hexdigest()
        # See if the feed has the same hash as last run
        old_feed = feed.session.query(RememberFeed).filter(RememberFeed.name == feed.name).first()
        if old_feed and old_feed.hash != config_hash:
            log.debug('Config has changed since last run, purging remembered entries.')
            feed.session.delete(old_feed)
            feed.session.flush()
            old_feed = None
        if not old_feed:
            feed.session.add(RememberFeed(name=feed.name, hash=config_hash))
            feed.session.flush()
        else:
            # Reject all the remembered entries
            for entry in feed.entries:
                for old_entry in old_feed.entries:
                    if entry['title'] == old_entry.title and entry.get('original_url') == old_entry.url:
                        feed.reject(entry, 'Rejected by %s plugin on a previous run' % old_entry.rejected_by)

    def on_entry_reject(self, feed, entry, remember=None, **kwargs):
        # We only remember rejections that specify the remember keyword argument
        if not remember:
            return
        if entry.get('imaginary'):
            log.debug('Not remembering rejection for imaginary entry `%s`' % entry['title'])
            return
        if not entry.get('title') or not entry.get('original_url'):
            log.debug('Can\'t remember rejection for entry without title or url.')
            return
        remember_feed = feed.session.query(RememberFeed).filter(RememberFeed.name == feed.name).first()
        remember_feed.entries.append(RememberEntry(title=entry['title'], url=entry['original_url'],
                                                   rejected_by=feed.current_plugin))
        feed.session.merge(remember_feed)
        feed.session.flush()


register_plugin(FilterRememberRejected, 'remember_rejected', builtin=True)
