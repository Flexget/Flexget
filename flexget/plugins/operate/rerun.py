import logging
from flexget import validator
from flexget.plugin import register_plugin

log = logging.getLogger('rerun')


class MaxReRuns(object):
    """Force a feed to rerun for debugging purposes."""

    def validator(self):
        root = validator.factory('boolean')
        return root

    def on_feed_start(self, feed, config):
        if config and not feed.is_rerun:
            log.debug('forcing a feed rerun')
            feed.rerun()


register_plugin(MaxReRuns, 'rerun', api_ver=2, debug=True)
