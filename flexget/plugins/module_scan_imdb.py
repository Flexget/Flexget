import re
import logging
from flexget.plugin import *

log = logging.getLogger('scan_imdb')

class PluginScanImdb:
    """
        Scan entry information for imdb url.
    """
    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_filter(self, feed):
        # check if disabled (value set to false)
        if 'scan_imdb' in feed.config:
            if not feed.config['scan_imdb']:
                return
            
        count = 0
        for entry in feed.entries:
            if not 'description' in entry:
                continue
            results = re.findall('(?:http://)?(?:www\.)?imdb.com/title/tt\d+', entry['description'])
            # not found any url
            if not results:
                return
            for result in results:
                entry['imdb_url'] = result
            count += 1
            log.debug('Found imdb url in description %s' % entry['imdb_url'])

        if count:
            log.debug('Found %s imdb urls from descriptions' % count)
            
register_plugin(PluginScanImdb, 'scan_imdb', builtin=True, priorities=dict(filter=200))
