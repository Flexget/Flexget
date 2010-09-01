import logging
import re
import urllib
from flexget.plugin import *

log = logging.getLogger('torrentz')

REGEXP = re.compile(r'http://www\.torrentz\.com/(?P<hash>[a-f0-9]{40})')


class UrlRewriteTorrentz(object):
    """Torrentz urlrewriter."""

    def url_rewritable(self, feed, entry):
        return REGEXP.match(entry['url'])
        
    def url_rewrite(self, feed, entry):
        hash = REGEXP.match(entry['url']).group(1)
        entry['url'] = 'http://zoink.it/torrent/%s.torrent' % hash.upper()

register_plugin(UrlRewriteTorrentz, 'torrentz', groups=['urlrewriter'])
