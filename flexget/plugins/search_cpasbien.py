from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import urllib2
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('search_cpasbien')

session = requests.Session()

CATEGORIES = {
	'films': 'films',
	'series': 'series',
	'mucic': 'musique',
	'films_fr': 'films-french',
	'720p': '720p',
	'series_fr': 'series-francaise',
	'dvdrip': 'films-dvdrip',
	'films_vostfr': 'films-vostfr',
	'1080p': '1080p',
	'series_vostfr': 'series-vostfr',
	'ebook': 'ebook'
}

categories = {
	'films',
	'series',
	'musique',
	'films-french',
	'720p',
	'series-francaise',
	'films-dvdrip',
	'films-vostfr',
	'1080p',
	'series-vostfr',
	'ebook'
}

class SearchCPASBIEN(object):
	schema = {
		'type': 'object',
		'properties': {
			'category': one_or_more({
				'oneOf': [
					{'type': 'integer'},
					{'type': 'string', 'enum': list(categories)},
				]})
		},
		'additionalProperties': False
	}

	@plugin.internet(log)
		
	def search(self, entry, config):
		"""
		CPASBIEN search plugin

		Config example:
		
			  tv_search_cpasbien:
				discover:
				  what:
					- trakt_list:
						username: xxxxxxx
						api_key: xxxxxxx
						series: watchlist
				  from:
					- cpasbien:
						category: "series-vostfr"
				  interval: 1 day
				  ignore_estimations: yes
				
		* Category is ONE of: films, series, musique, films-french, 1080p, 720p, series-francaise, films-dvdrip, films-vostfr, series-vostfr, ebook
		
		"""

		category_url_fragment = '%s' % config['category']

		base_url = 'http://www.cpasbien.pe/'

		entries = set()
		for search_string in entry.get('search_strings', [entry['title']]):
			search_string = search_string.replace(' ', '-').lower()
			search_string = search_string.replace('(', '')
			search_string = search_string.replace(')', '')
			query = normalize_unicode(search_string)
			query_url_fragment = query.encode('iso-8859-1')

			# http://www.cpasbien.pe/recherche/ncis.html
			url = (base_url + "recherche/" + category_url_fragment + '/' + query_url_fragment)
			log.debug('CPABIEN search url: %s' % url + '.html')
			
			# GET URL
			opener = urllib2.build_opener()
			opener.addheaders.append(("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/14.0.835.202 Safari/535.1"))
			f = opener.open(url + '.html')

			soup = get_soup(f)
			
			if soup.findAll(text="Pas de torrents disponibles correspondant"): 
				log.debug('search returned no results')
			else:
				
				nextpage = 0
				while (nextpage >= 0):
					if (nextpage > 0):
						newurl = (url + '/page-' + str(nextpage) )
						log.debug('-----> PAGE SUIVANTE : %s' % newurl)
						f1 = opener.open(newurl)
						soup = get_soup(f1)
					
					for result in soup.findAll('div', attrs={'class': re.compile('ligne')}):
						entry = Entry()
						link = result.find('a', attrs={'href': re.compile('dl-torrent')})
						entry['title'] = link.contents[0]
						
						#REWRITE URL
						#http://www.cpasbien.pe/dl-torrent/series/0-a-b/awake-s01e13-final-vostfr-hdtv.html
						#http://www.cpasbien.pe/telecharge/awake-s01e13-final-vostfr-hdtv.torrent
						
						page_link = link.get('href')
						link_rewrite = page_link.split("/")
						# get last value in array remove .html and replace by .torrent
						endlink = link_rewrite[-1]
						entry['url'] = ( base_url + "telecharge/" + endlink[:-5] + ".torrent")
						
						log.debug('URL: %s' % (page_link) )
						log.debug('REW: %s' % (entry['url']) )
						
						log.debug('Title: %s | DL LINK: %s' % (entry['title'], entry['url']) )
						
						entry['torrent_seeds'] = int(result.find('span', attrs={'class': re.compile('seed')}).text)
						entry['torrent_leeches'] = int(result.find('div', attrs={'class': re.compile('down')}).text)
						
						sizefull = result.find('div', attrs={'class': re.compile('poid')}).text

						size = sizefull[:-3]
						unit = sizefull[-2:]
						
						if unit == 'GB':
							entry['content_size'] = int(float(size) * 1024)
						elif unit == 'MB':
							entry['content_size'] = int(float(size))
						elif unit == 'KB':
							entry['content_size'] = int(float(size) / 1024)
						if(entry['torrent_seeds'] > 0):
							entries.add(entry)
						else:
							log.debug('0 SEED, not adding entry')
					
					if soup.find(text=re.compile("Suiv")):
						nextpage += 1
					else:
						nextpage = -1
							
			return entries

@event('plugin.register')
def register_plugin():
    plugin.register(SearchCPASBIEN, 'CPASBIEN', groups=['search'], api_ver=2)