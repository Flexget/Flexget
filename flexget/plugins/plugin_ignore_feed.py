import logging
from flexget.plugin import register_plugin

log = logging.getLogger('ignore_feed')


class IgnoreFeed(object):

    """Only execute feed when specified with --feed"""

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_start(self, feed):
        # Make sure we need to run
        if not feed.config['ignore_feed']:
            return
        onlyfeed = feed.manager.options.onlyfeed
        if not (onlyfeed and feed.name.lower() == onlyfeed.lower()):
            log.debug('Disabling feed %s' % feed.name)
            feed.enabled = False

register_plugin(IgnoreFeed, 'ignore_feed')
