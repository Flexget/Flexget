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
            quals = qualities.all()
            for quality in quals:
                for field_name, field_value in entry.iteritems():
                    if not isinstance(field_value, basestring):
                        continue
                    if quality.name.lower() in field_value.lower():
                        quality_name = qualities.common_name(quality.name)
                        entry['quality'] = quality_name
                        log.log(5, 'Found quality %s (%s) for %s from field %s' % \
                            (quality_name, quality.name, entry['title'], field_name))
                        break
                if 'quality' in entry:
                    break
            
register_plugin(MetainfoQuality, 'metainfo_quality', builtin=True)
