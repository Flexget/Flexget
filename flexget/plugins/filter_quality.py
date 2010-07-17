import logging
from flexget.plugin import *

log = logging.getLogger('quality')


class FilterQuality(object):
    """
        Rejects all entries that don't have one of the specified qualities
        
        Example:
        
        quality:
          - hdtv
    """

    def validator(self):
        from flexget import validator
        import flexget.utils.qualities

        qualities = [q.name for q in flexget.utils.qualities.all()]

        root = validator.factory()
        root.accept('choice').accept_choices(qualities)
        root.accept('list').accept('choice').accept_choices(qualities)
        return root

    def on_feed_filter(self, feed):
        config = feed.config.get('quality', None)
        if isinstance(config, basestring):
            config = [config]
        for entry in feed.entries:
            if entry.get('quality') not in config:
                feed.reject(entry, 'quality is %s' % entry['quality'])

register_plugin(FilterQuality, 'quality')
