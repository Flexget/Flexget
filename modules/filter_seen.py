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
        manager.register('seen', builtin=True, filter_priority=255)

        # remember and filter by these fields
        self.fields = ['original_url', 'title', 'url']

    def validate(self, config):
        if not isinstance(config, bool):
            return ['wrong datatype, expecting bool']
        return []

    def feed_filter(self, feed):
        """Filter seen entries"""
        duplicates = []
        for entry in feed.entries:
            for field in self.fields:
                if not entry.has_key(field):
                    continue
                # note: urllib.unquote is only for making module backwards compatible
                if feed.shared_cache.get(entry[field], False) or feed.shared_cache.get(urllib.unquote(entry[field]), False):
                    log.debug("Rejecting '%s' '%s' because of seen '%s'" % (entry['url'], entry['title'], field))
                    feed.reject(entry)

            # scan for duplicates
            for duplicate in feed.entries:
                if entry == duplicate or entry in duplicates: 
                    continue
                for field in self.fields:
                    if field in ['title']:
                        # allow duplicates with these fields
                        continue
                    if entry.get(field, object()) == duplicate.get(field, object()):
                        log.debug('Rejecting %s because of duplicate field %s' % (duplicate['title'], field))
                        feed.reject(duplicate)
                        # TODO: if / when entry has multiple entries it should combine these two entries
                        # now the duplicate is just rejected and considered seen
                        feed.shared_cache.store(duplicate[field], True, 365)
                        duplicates.append(duplicate)
                    

    def feed_exit(self, feed):
        """Remember succeeded entries"""
        for entry in feed.entries:
            for field in self.fields:
                if not entry.has_key(field):
                    continue
                feed.shared_cache.store(entry[field], True, 365)
            
            # verbose if in learning mode
            if feed.manager.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))
            else:
                log.debug("Learned '%s' '%s' (will skip this in the future)" % (entry['url'], entry['title']))
