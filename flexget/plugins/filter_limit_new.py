import logging
from flexget.plugin import *

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

    def validator(self):
        from flexget import validator

        return validator.factory('number')

    @priority(-255)
    def on_feed_filter(self, feed):
        amount = feed.config.get('limit_new', len(feed.entries))
        i = 1
        rejected = 0
        passed = []
        for entry in feed.accepted + [i for i in feed.entries if i not in feed.accepted]:
            # if entry is marked as passed, don't remove it
            # this is because we used accepted + entries and it may be listed in both ..
            if entry in passed:
                continue
            if i > amount:
                rejected += 1
                feed.reject(entry, 'limit exceeded')
            else:
                passed.append(entry)
                feed.verbose_progress('Passed %s (%s)' % (entry['title'], entry['url']))
            i += 1
        log.debug('Rejected: %s Passed: %s' % (rejected, len(passed)))

register_plugin(FilterLimitNew, 'limit_new')
