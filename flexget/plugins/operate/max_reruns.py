import logging
from flexget import validator
from flexget.feed import Feed
from flexget.plugin import register_plugin

log = logging.getLogger('max_reruns')


class MaxReRuns(object):
    """Overrides the maximum amount of re-runs allowed by a feed."""

    def __init__(self):
        self.default = Feed.max_reruns

    def validator(self):
        root = validator.factory('integer')
        return root

    def on_feed_start(self, feed, config):
        self.default = feed.max_reruns
        feed.max_reruns = config
        log.debug('changing max feed rerun variable to: %s' % config)

    def on_feed_exit(self, feed, config):
        log.debug('restoring max feed rerun variable to: %s' % self.default)
        feed.max_reruns = self.default

    on_feed_abort = on_feed_exit


register_plugin(MaxReRuns, 'max_reruns', api_ver=2)
