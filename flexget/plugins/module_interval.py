import logging
import datetime
from flexget.plugin import *

log = logging.getLogger('interval')


class PluginInterval:

    """
        Allows specifying minimum interval for feed execution.

        Format: [n] [minutes|hours|days|months]
        
        Example:
        
        interval: 7 days
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('regexp_match')
        root.accept('\d+ (minutes|hours|days|weeks)')
        return root

    def on_feed_start(self, feed):
        if feed.manager.options.interval_ignore or feed.manager.options.learn:
            log.info('Ignoring feed %s interval' % feed.name)
            return
        last_time = feed.simple_persistence.setdefault('last_time', datetime.datetime.now())
        log.debug('last_time: %s' % repr(last_time))
        amount, unit = feed.config.get('interval').split(' ')
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit: int(amount)}
        try:
            next_time = last_time + datetime.timedelta(**params)
        except TypeError:
            raise PluginWarning('Invalid time format', log)
        log.debug('next_time: %s' % repr(next_time))
        if datetime.datetime.now() < next_time:
            log.debug('interval not met')
            feed.verbose_progress('Interval %s not met on feed %s. Use --now to override.' % (feed.config.get('interval'), feed.name), log)
            feed.abort(silent=True)
        else:
            log.debug('interval passed')
            feed.simple_persistence.set('last_time', datetime.datetime.now())

register_plugin(PluginInterval, 'interval')
register_parser_option('--now', action='store_true', dest='interval_ignore', default=False,
                       help='Ignore interval(s)')
