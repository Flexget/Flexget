import logging
from flexget.plugin import register_plugin

log = logging.getLogger('priority')


class FeedPriority(object):

    """Set feed priorities"""

    def validator(self):
        from flexget import validator
        return validator.factory('integer')

    def on_process_start(self, feed, config):
        feed.priority = feed.config.get('priority', 65535)

register_plugin(FeedPriority, 'priority', api_ver=2)
