import logging
from flexget.utils.log import log_once
from flexget.plugin import register_plugin, register_parser_option, priority
from flexget.feed import log as feed_log

log = logging.getLogger('verbose')


class Verbose(object):

    """
    Verbose entry accept, reject and failure
    """

    def on_entry_accept(self, feed, entry, reason='', **kwargs):
        self.verbose_details(feed, action='Accepted', title=entry['title'], reason=reason)

    def on_entry_reject(self, feed, entry, reason='', **kwargs):
        self.verbose_details(feed, action='Rejected', title=entry['title'], reason=reason)

    def on_entry_fail(self, feed, entry, reason='', **kwargs):
        self.verbose_details(feed, action='Failed', title=entry['title'], reason=reason)

    def verbose_details(self, feed, **kwarg):
        if feed.manager.options.silent:
            return
        kwarg['plugin'] = feed.current_plugin
        kwarg['action'] = kwarg['action'].upper()

        if kwarg['reason'] is None:
            msg = "%(action)s: `%(title)s` by %(plugin)s plugin"
        else:
            # lower capitalize first letter of reason
            if kwarg['reason'] and len(kwarg['reason']) > 2:
                kwarg['reason'] = kwarg['reason'][0].lower() + kwarg['reason'][1:]
            msg = "%(action)s: `%(title)s` by %(plugin)s plugin because %(reason)s"

        feed_log.verbose(msg % kwarg)

    def on_feed_exit(self, feed):
        if feed.manager.options.silent:
            return
        # verbose undecided entries
        if feed.manager.options.verbose:
            for entry in feed.entries:
                if entry in feed.accepted:
                    continue
                log.verbose('UNDECIDED: `%s`' % entry['title'])

    @priority(-512)
    def on_process_end(self, feed):
        if feed.manager.options.silent:
            return
        if feed.manager.options.verbose:
            log_once('About undecided entries: They were created by input plugins but were not accepted because '
                     'no (filter) plugin accepted them. If you want them to reach output, configure filters.',
                     logger=log)

register_plugin(Verbose, 'verbose', builtin=True)
register_parser_option('-v', '--verbose', action='store_true', dest='verbose', default=False,
                       help='Verbose undecided entries.')
register_parser_option('-s', '--silent', action='store_true', dest='silent', default=False,
                       help='Don\'t verbose any actions (accept, reject, fail).')
