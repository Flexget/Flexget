import re
import logging

log = logging.getLogger('scan_imdb')

class PluginScanImdb:

    """
        Scan entry information for imdb url.
    """

    __plugin__ = 'scan_imdb'
    __plugin_builtin__ = True
    __priorities__ = {
        'filter': 200
    }

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
