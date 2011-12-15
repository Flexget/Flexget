import logging
from flexget import validator
from flexget.plugin import register_plugin

log = logging.getLogger('max_reruns')


class MaxReRuns(object):
    """Overrides the maximum amount of re-runs allowed by a feed."""

    def validator(self):
        root = validator.factory('integer')
        return root

    def on_process_start(self, feed, config):
        feed.max_reruns = config
        log.debug('changing max feed rerun variable to: %s' % config)

register_plugin(MaxReRuns, 'max_reruns', api_ver=2)
