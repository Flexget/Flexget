import urllib
import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('seen')

class FilterSeen:

    """
        Remembers previously downloaded content and rejects them in
        subsequent executions. Without this module FlexGet would
        download all matching content on every execution.

        This module is enabled on all feeds by default.
        See wiki for more information.
    """

    def register(self, manager, parser):
        manager.register(event='filter', keyword='seen', callback=self.filter_seen, order=-100, builtin=True)
        manager.register(event='exit', keyword='seen', callback=self.learn_succeeded, builtin=True)

        # remember and filter by these fields
        self.fields = ['original_url', 'title']

    def validate(self, config):
        if not isinstance(config, bool):
            return ['wrong datatype, expecting bool']
        return []

    def filter_seen(self, feed):
        for entry in feed.entries:
            for field in self.fields:
                if not entry.has_key(field):
                    continue
                # note: urllib.unquote is only for making module backwards compatible
                if feed.shared_cache.get(entry[field], False) or feed.shared_cache.get(urllib.unquote(entry[field]), False):
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], field))
                    feed.reject(entry)

    def learn_succeeded(self, feed):
        for entry in feed.get_succeeded_entries():
            for field in self.fields:
                if not entry.has_key(field):
                    continue
                feed.shared_cache.store(entry[field], True, 365)
            
            # verbose if in learning mode
            if feed.manager.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))
            else:
                log.debug("Learned '%s' '%s' (will skip this in the future)" % (entry['url'], entry['title']))
