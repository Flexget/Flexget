import logging
from flexget.plugin import *
from flexget.utils.titles.parser import TitleParser

log = logging.getLogger('metainfo_quality')


class MetainfoQuality:
    """
    Utility:

    Set quality attribute for entries.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_metainfo(self, feed):
        # check if disabled (value set to false)
        if 'metainfo_quality' in feed.config:
            if not feed.config['metainfo_quality']:
                return
        
        for entry in feed.entries:
            for quality in TitleParser.qualities:
                for field_name, field_value in entry.iteritems():
                    if not isinstance(field_value, basestring):
                        continue
                    if quality.lower() in field_value.lower():
                        log.log(5, 'Found quality %s for %s from field %s' % \
                            (quality, entry['title'], field_name))
                        entry['quality'] = quality
                        break
                if 'quality' in entry:
                    break
            
register_plugin(MetainfoQuality, 'metainfo_quality', builtin=True)
