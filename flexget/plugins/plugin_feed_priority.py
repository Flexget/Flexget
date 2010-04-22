import logging
from flexget.plugin import plugins, FEED_EVENTS, EVENT_METHODS
from flexget.plugin import *

log = logging.getLogger('priority')


class FeedPriority(object):

    """
        Set feed priorities
    """

    def validator(self):
        from flexget import validator
        return validator.factory('number')

    def on_process_start(self, feed):
        feed.priority = feed.config.get('priority', 0)

register_plugin(FeedPriority, 'priority')
