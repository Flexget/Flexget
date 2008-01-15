__instance__ = 'SeenFilter'

import urllib
import logging

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
            if feed.cache.get(entry_url, False) or feed.cache.get(entry['title'], False):
                logging.debug("Seen: filtering '%s' '%s'" % (entry_url, entry['title']))
                feed.filter(entry)

    def learn_succeeded(self, feed):
        for entry in feed.get_succeeded_entries():
            # add title and entry url to seen list
            entry_url = urllib.unquote(entry['url'])
            
            feed.cache.store(entry['title'], True, 120)
            feed.cache.store(entry_url, True, 120)
            
            # verbose if in learning mode
            if feed.manager.options.learn:
                logging.info("Learned '%s' (skipped in future)" % (entry['title']))
            else:
                logging.debug("SeenFilter: learned '%s' '%s' (skipped in future)" % (entry_url, entry['title']))
