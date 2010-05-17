import logging
from flexget.plugin import *
from flexget.utils import qualities

log = logging.getLogger('metainfo_quality')


class MetainfoQuality(object):
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
            found_quality = qualities.UnknownQuality()
            for qualname, quality in qualities.registry.iteritems():
                for field_name, field_value in entry.iteritems():
                    if not isinstance(field_value, basestring):
                        continue
                    if qualname.lower() in field_value.lower():
                        if quality > found_quality:
                            found_quality = quality
            entry['quality'] = found_quality.name
            log.log(5, 'Found quality %s (%s) for %s from field %s' % \
            (entry['quality'], quality, entry['title'], field_name))
                            
            
register_plugin(MetainfoQuality, 'metainfo_quality', builtin=True)
