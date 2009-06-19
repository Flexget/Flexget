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

    def feed_filter(self, feed):
        # check if disabled (value set to false)
        if 'scan_imdb' in feed.config:
            if not feed.config['scan_imdb']:
                return
        # scan
        for entry in feed.entries:
            if not 'description' in entry:
                continue
            results = re.findall('(?:http://)?(?:www\.)?imdb.com/title/tt\d+', entry['description'])
            # not found any url
            if not results:
                return
            for result in results:
                entry['imdb_url'] = result
            log.info('Found imdb url in description %s' % entry['imdb_url'])

register_plugin(PluginScanImdb, 'scan_imdb', builtin=True, priorities=dict(filter=200))
