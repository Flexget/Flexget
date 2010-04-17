import re
import logging
from flexget.plugin import *

log = logging.getLogger('metainfo_imdb_url')


class MetainfoImdbUrl(object):
    """
        Scan entry information for imdb url.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_metainfo(self, feed):
        # check if disabled (value set to false)
        if 'scan_imdb' in feed.config:
            if not feed.config['scan_imdb']:
                return

        for entry in feed.entries:
            if not 'description' in entry:
                continue
            urls = re.findall(r'\bimdb.com/title/tt\d+\b', entry['description'])
            if not urls:
                continue

            # Uniquify the list of urls.
            urls = list(set(urls))
            if 1 < len(urls):
                log.debug('Found multiple imdb urls; not using any of: %s' %
                    ' '.join(urls))
                continue

            url = ''.join(['http://www.', urls[0]])
            entry['imdb_url'] = url
            log.debug('Found imdb url in description %s' % url)

register_plugin(MetainfoImdbUrl, 'scan_imdb', builtin=True)
