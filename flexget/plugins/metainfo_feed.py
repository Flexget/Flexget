import logging
from flexget.plugin import *
from flexget.utils.titles.parser import TitleParser

log = logging.getLogger('metainfo_feed')


class MetainfoFeed:
    """
    Utility:

    Set feed attribute for entries.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_metainfo(self, feed):
        # check if disabled (value set to false)
        if 'metainfo_feed' in feed.config:
            if not feed.config['metainfo_feed']:
                return
        
        for entry in feed.entries:
            entry['feed'] = feed.name
            
register_plugin(MetainfoFeed, 'metainfo_feed', builtin=True)
