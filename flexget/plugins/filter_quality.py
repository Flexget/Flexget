import logging
from flexget.plugin import *

log = logging.getLogger('quality')


class FilterQuality:
    """
        Rejects all entries that don't have one of the specified qualities
        
        Example:
        
        quality:
          - hdtv
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        root.accept('list').accept('text')
        return root

    def on_feed_filter(self, feed):
        config = feed.config.get('quality', None)
        if isinstance(config, basestring):
            config = [config]
        for entry in feed.entries:
            if entry.get('quality') not in config:
                feed.reject(entry, 'quality is %s' % entry['quality'])

register_plugin(FilterQuality, 'quality')
