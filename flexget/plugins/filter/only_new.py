import logging
from flexget.plugin import register_plugin, get_plugin_by_name

log = logging.getLogger('only_new')


class FilterOnlyNew(object):
    """Causes input plugins to only emit entries that haven't been seen on previous runs."""

    def validator(self):
        from flexget.validator import BooleanValidator
        return BooleanValidator()

    def on_process_start(self, feed, config):
        """Make sure the remember_rejected plugin is available"""
        # Raises an error if plugin isn't available
        get_plugin_by_name('remember_rejected')

    def on_feed_exit(self, feed, config):
        """Reject all entries so remember_rejected will reject them next time"""
        if not config or not feed.entries:
            return
        log.verbose('Rejecting entries after the feed has run so they are not processed next time.')
        for entry in feed.entries:
            feed.reject(entry, 'Already processed entry', remember=True)


register_plugin(FilterOnlyNew, 'only_new', api_ver=2)
