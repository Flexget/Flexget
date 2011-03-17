import logging
from flexget.plugin import register_plugin, priority, DependencyError, get_plugin_by_name

log = logging.getLogger('limit_new')


class FilterLimitNew(object):
    """
        Limit number of new items.

        Example:

        limit_new: 1

        This would allow only one new item to pass trough per execution.
        Useful for passing torrents slowly into download.

        Note that since this is per execution, actual rate depends how often
        FlexGet is executed.
    """

    def __init__(self):
        self.backlog = None

    def validator(self):
        from flexget import validator
        return validator.factory('integer')

    def on_process_start(self, feed):
        try:
            self.backlog = get_plugin_by_name('backlog').instance
        except DependencyError:
            log.warning('Unable utilize backlog plugin, entries may slip trough limit_new in some rare cases')

    @priority(-255)
    def on_feed_filter(self, feed):
        if feed.manager.options.learn:
            log.info('Plugin limit_new is disabled with --learn / --reset')
            return

        amount = feed.config.get('limit_new', len(feed.entries))
        i = 1
        rejected = 0
        passed = []
        for entry in feed.accepted + [e for e in feed.entries if e not in feed.accepted]:
            # if entry is marked as passed, don't remove it
            # this is because we used accepted + entries and it may be listed in both ..
            if entry in passed:
                continue
            if i > amount:
                rejected += 1
                feed.reject(entry, 'limit exceeded')
                if self.backlog:
                    self.backlog.add_backlog(feed, entry, '48 hours')
            else:
                passed.append(entry)
                log.verbose('Allowed %s (%s)' % (entry['title'], entry['url']))
            i += 1
        log.debug('Rejected: %s Allowed: %s' % (rejected, len(passed)))

register_plugin(FilterLimitNew, 'limit_new')
