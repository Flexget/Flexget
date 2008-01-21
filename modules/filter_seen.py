import urllib
import logging

log = logging.getLogger('seen')

class SeenFilter:

    """
        Remembers previously downloaded content and skips then in
        subsequent executions. Without this module FlexGet will
        download all matching content on every execution.

        This module is enabled on all feeds by default.
        See wiki for more information.
    """

    def register(self, manager, parser):
        manager.register(instance=self, type="filter", keyword="seen", callback=self.filter_seen, order=-100, builtin=True)
        manager.register(instance=self, type="exit", keyword="seen", callback=self.learn_succeeded, builtin=True)

    def filter_seen(self, feed):
        for entry in feed.entries:
            entry_url = urllib.unquote(entry['url'])
            if feed.shared_cache.get(entry_url, False) or feed.shared_cache.get(entry['title'], False):
                log.debug("Seen: filtering '%s' '%s'" % (entry_url, entry['title']))
                feed.filter(entry, True) # True removes this entry unconditionally ASAP

    def learn_succeeded(self, feed):
        for entry in feed.get_succeeded_entries():
            # add title and entry url to seen list
            entry_url = urllib.unquote(entry['url'])
            
            feed.shared_cache.store(entry['title'], True, 120)
            feed.shared_cache.store(entry_url, True, 120)
            
            # verbose if in learning mode
            if feed.manager.options.learn:
                log.info("Learned '%s' (skipped in future)" % (entry['title']))
            else:
                log.debug("Learned '%s' '%s' (skipped in future)" % (entry_url, entry['title']))
