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

    def register(self, manager):
        manager.register(instance=self, type="filter", keyword="seen", callback=self.filter_seen, order=-100, builtin=True)
        manager.register(instance=self, type="exit", keyword="seen", callback=self.learn_succeeded, builtin=True)

    def get_session(self, feed):
        """Initialize  and return global session, this is shared between all feeds"""
        feed.global_session.setdefault('filter_seen', [])
        return feed.global_session['filter_seen']

    def filter_seen(self, feed):
        seen = self.get_session(feed)
        for entry in feed.entries:
            entry_url = urllib.unquote(entry['url'])
            if entry_url in seen or entry['title'] in seen:
                logging.debug("Seen: filtering '%s' '%s'" % (entry_url, entry['title']))
                feed.filter(entry)

    def learn_succeeded(self, feed):
        seen = self.get_session(feed)
        for entry in feed.get_succeeded_entries():
            # add title and entry url to seen list
            entry_url = urllib.unquote(entry['url'])
            seen.append(entry['title'])
            seen.append(entry_url)
            if feed.manager.options.learn:
                logging.info("Learned '%s' (skipped in future)" % (entry['title']))
            else:
                logging.debug("SeenFilter: learned '%s' '%s' (skipped in future)" % (entry_url, entry['title']))
            # if entries has grown too big, remove some of the old ones
            while len(seen) > 5000:
                seen.pop(0)          
