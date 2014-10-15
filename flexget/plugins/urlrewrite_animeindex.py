from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils.requests import Session
from flexget.utils.soup import get_soup

log = logging.getLogger('animeindex')

requests = Session()
requests.headers.update({'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'})
requests.set_domain_delay('imdb.com', '2 seconds')


class UrlRewriteAnimeIndex(object):
    """AnimeIndex urlrewriter."""

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://tracker.anime-index.org/index.php?page=torrent-details&id=')

    def url_rewrite(self, task, entry):
	entry['url'] = self.parse_download_page(entry['url'])
		
	#http://tracker.anime-index.org/index.php?page=torrent-details&id=b8327fdf9003e87446c8b3601951a9a65526abb2
		
	#http://tracker.anime-index.org/download.php?id=b8327fdf9003e87446c8b3601951a9a65526abb2	#http://tracker.anime-index.org/download.php?id=b8327fdf9003e87446c8b3601951a9a65526abb2&f=[DeadFish]%20Yowamushi%20Pedal:%20Grande%20Road%20-%2002%20[720p][AAC].mp4.torrent
	
    def parse_download_page(self, url):
	log.error("Got the URL: %s" % url)
	page = requests.get(url)
	try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)
	torrent_first_part = url.replace('index.php?page=torrent-details&', 'download.php?')
	torrent_id = torrent_first_part.replace('http://tracker.anime-index.org/download.php?', '')
	log.error("Replace URL: %s" % torrent_id)
	regexp_torrent = "\?" + torrent_id + "(.+)\""
	log.error("Regexp: %s" % regexp_torrent)
	torrent_id_prog = re.compile(regexp_torrent)
	#r = torrent_id_prog.search(page)
	#log.error("Regexp testr: %s" % r)
	#test = soup.findAll(torrent_id_prog)
	try:
	    test = torrent_id_prog.findall(page.text)
	except Exception as e:
            raise UrlRewritingError(e)
	log.error("Regexp test: %s" % test)
	murl = torrent_first_part + test[0]
	murl = murl.replace('&amp;','&')
	log.error("Regexp murl: %s" % murl)
	return murl

@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteAnimeIndex, 'animeindex', groups=['urlrewriter'], api_ver=2)