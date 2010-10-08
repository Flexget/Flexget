import logging
from flexget.plugin import *

log = logging.getLogger('manual')


class PluginManual(object):

    """
        Allows disabling manual fetching per feed

        Format: yes / no
        
        Example:
        
        manual: no
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        return root

    def on_feed_start(self, feed):
        if feed.manager.options.onlyfeed:
            log.info('Manual run of feed %s' % feed.name)
            return

        manual = feed.config.get('manual')

        if manual:
            feed.verbose_progress('Skipping automatic run of feed %s' % (feed.name))
            feed.verbose_progress('run with --feed %s to force run' % (feed.name))
            feed.abort(silent=True)

register_plugin(PluginManual, 'manual')
