import logging
import re
import math
from flexget.plugin import *
from flexget.utils import qualities

log = logging.getLogger('metainfo_csize')

SIZE_RE = re.compile(r'Size[^\d]{0,7}([\.,\d]+).{0,5}(MB|GB)', re.IGNORECASE)


class MetainfoContentSize(object):
    """
    Utility:

    Check if content size is mentioned in description and set content_size attribute for entries if it is
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_metainfo(self, feed):
        # check if disabled (value set to false)
        if 'metainfo_content_size' in feed.config:
            if not feed.config['metainfo_content_size']:
                return

        count = 0
        for entry in feed.entries:
            match = SIZE_RE.search(entry.get('description', ''))
            if match:
                amount = match.group(1).replace(',', '.')
                unit = match.group(2).lower()
                count += 1
                if unit == 'gb':
                    amount = math.ceil(float(amount) * 1024)
                log.log(5, 'setting content size to %s' % amount)
                entry['content_size'] = int(amount)
                
        if count:
            log.info('Found content size information from %s entries' % count)
                            
            
register_plugin(MetainfoContentSize, 'metainfo_content_size', builtin=True)
