import logging
import fnmatch
from flexget.plugin import register_plugin, register_parser_option, PluginError

log = logging.getLogger('feed_control')


class OnlyFeed(object):
    """
        Implements --feed option to only run specified feed(s)

        Example:
        flexget --feed feeda

        Multiple feeds:
        flexget --feed feeda,feedb

        Patterns:
        flexget --feed 'tv*'
    """

    def on_process_start(self, feed):
        # If --feed hasn't been specified don't do anything
        if not feed.manager.options.onlyfeed:
            return

        # Make a list of the specified feeds to run, and those available
        onlyfeeds = feed.manager.options.onlyfeed.split(',')

        # Make sure the specified feeds exist
        enabled_feeds = [f.name.lower() for f in feed.manager.feeds.itervalues() if f.enabled]
        for onlyfeed in onlyfeeds:
            if any(i in onlyfeed for i in '*?['):
                # Try globbing
                if not any(fnmatch.fnmatchcase(f.lower(), onlyfeed.lower()) for f in enabled_feeds):
                    feed.manager.disable_feeds()
                    raise PluginError('No match for feed pattern \'%s\'' % onlyfeed, log)
            elif onlyfeed.lower() not in enabled_feeds:
                # If any of the feeds do not exist, exit with an error
                feed.manager.disable_feeds()
                raise PluginError('Could not find feed \'%s\'' % onlyfeed, log)

        # If current feed is not among the specified feeds, disable it
        if not any(feed.name.lower() == f.lower() or fnmatch.fnmatchcase(feed.name.lower(), f.lower())
                for f in onlyfeeds):
            feed.enabled = False


class ManualFeed(object):
    """Only execute feed when specified with --feed"""

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_start(self, feed):
        # Make sure we need to run
        if not feed.config['manual']:
            return
        # If --feed hasn't been specified disable this plugin
        if not feed.manager.options.onlyfeed:
            log.debug('Disabling feed %s' % feed.name)
            feed.enabled = False

register_plugin(OnlyFeed, '--feed', builtin=True)
register_plugin(ManualFeed, 'manual')
register_parser_option('--feed', action='store', dest='onlyfeed', default=None, metavar='FEED[,...]', 
                       help='Run only specified feed(s), optionally using glob patterns ("tv-*").'
                            ' Matching is case-insensitive.')
