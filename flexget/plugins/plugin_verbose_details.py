from flexget.plugin import register_plugin, priority
import logging

log = logging.getLogger('details')


class PluginDetails(object):

    def on_feed_start(self, feed):
        # Make a flag for feeds to declare if it is ok not to produce entries
        feed.no_entries_ok = False

    @priority(-512)
    def on_feed_input(self, feed):
        if not feed.entries:
            if feed.no_entries_ok:
                log.verbose('Feed didn\'t produce any entries.')
            else:
                log.verbose('Feed didn\'t produce any entries. This is likely due to a mis-configured or non-functional input.')
        else:
            log.verbose('Produced %s entries.' % (len(feed.entries)))

    @priority(-512)
    def on_feed_download(self, feed):
        # Needs to happen as the first in download, so it runs after urlrewrites
        # and IMDB queue acceptance.
        log.verbose('Summary - Accepted: %s (Rejected: %s Undecided: %s Failed: %s)' %
            (len(feed.accepted), len(feed.rejected),
            len(feed.entries) - len(feed.accepted), len(feed.failed)))


register_plugin(PluginDetails, 'details', builtin=True)
