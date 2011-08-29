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
            self.get_quality(entry)

    def field_order(self, x):
        """helper function, iterate entry fields in certain order"""
        order = ['title', 'description']
        return order.index(x[0]) if x[0] in order else len(order)

    def get_quality(self, entry):
        quality, field_name = None, None
        for field_name, field_value in sorted(entry.items(), key=self.field_order):
            if not isinstance(field_value, basestring):
                continue
            # ignore some fields ...
            if field_name in ['feed']:
                continue
            quality = qualities.parse_quality(field_value)
            if quality > qualities.UNKNOWN:
                # if we find a quality in this field, stop searching
                break
        if quality is None or field_name is None:
            return entry
        entry['quality'] = quality
        if quality is not qualities.UNKNOWN:
            log.trace('Found quality %s (%s) for %s from field %s' % \
                (entry['quality'], quality, entry['title'], field_name))
        return entry

register_plugin(MetainfoQuality, 'metainfo_quality', builtin=True)
