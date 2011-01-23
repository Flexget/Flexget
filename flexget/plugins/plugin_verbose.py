import logging
from flexget.plugin import *

log = logging.getLogger('verbose')


class Verbose(object):

    """
        Enables verbose log output.

        Prints a line in the log when entries are accepted, rejected or failed.
        Contains phase, plugin and reason for action.
    """

    def on_entry_accept(self, feed, entry, reason):
        self.verbose_details(feed, 'Accepted %s' % entry['title'], reason)

    def on_entry_reject(self, feed, entry, reason):
        self.verbose_details(feed, 'Rejected %s' % entry['title'], reason)

    def on_entry_fail(self, feed, entry, reason):
        self.verbose_details(feed, 'Failed %s' % entry['title'], reason)

    def verbose_details(self, feed, msg, reason=''):
        """Verbose if verbose option is enabled"""
        reason_str = ''
        if reason:
            reason_str = ' (%s)' % reason
        if feed.manager.options.verbose:
            try:
                print "+ %-8s %-12s %s%s" % (feed.current_phase, feed.current_plugin, msg, reason_str)
            except:
                print "+ %-8s %-12s %s%s (warning: unable to print unicode)" % \
                    (feed.current_phase, feed.current_plugin, repr(msg), reason_str)
        else:
            log.debug('phase: %s plugin: %s msg: %s%s' % \
                (feed.current_phase, feed.current_plugin, msg, reason_str))

    def on_feed_exit(self, feed):
        # verbose undecided entries
        if feed.manager.options.verbose:
            for entry in feed.entries:
                if entry in feed.accepted:
                    continue
                try:
                    print "+ %-8s %-12s %s" % ('undecided', '', entry['title'])
                except:
                    print "+ %-8s %-12s %s (warning: unable to print unicode)" % ('undecided', '', repr(entry['title']))

register_plugin(Verbose, 'verbose', builtin=True)
register_parser_option('-v', '--verbose', action='store_true', dest='verbose', default=False,
    help='Verbose process. Display entry accept and reject info. Very useful for viewing what happens in feed(s).')
