from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils.requests import Session

log = logging.getLogger('animeindex')

requests = Session()
requests.headers.update({'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'})
requests.set_domain_delay('imdb.com', '2 seconds')

#http://tracker.anime-index.org/index.php?page=torrent-details&id=b8327fdf9003e87446c8b3601951a9a65526abb2
#http://tracker.anime-index.org/download.php?id=b8327fdf9003e87446c8b3601951a9a65526abb2&f=[DeadFish]%20Yowamushi%20Pedal:%20Grande%20Road%20-%2002%20[720p][AAC].mp4.torrent

class UrlRewriteAnimeIndex(object):
    """AnimeIndex urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://tracker.anime-index.org/index.php?page=torrent-details&id=')

    def url_rewrite(self, task, entry):
	entry['url'] = self.parse_download_page(entry['url'])
	
    def parse_download_page(self, url):
	page = requests.get(url)
	torrent_first_part = url.replace('index.php?page=torrent-details&', 'download.php?')
	torrent_id = torrent_first_part.replace('http://tracker.anime-index.org/download.php?', '')
	regexp_torrent = "\?" + torrent_id + "(.+)\""
	torrent_id_prog = re.compile(regexp_torrent)
	test = torrent_id_prog.findall(page.text)
	murl = torrent_first_part + test[0]
	murl = murl.replace('&amp;','&')
	log.info("Regexp murl: %s" % murl)
	return murl

@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteAnimeIndex, 'animeindex', groups=['urlrewriter'], api_ver=2)