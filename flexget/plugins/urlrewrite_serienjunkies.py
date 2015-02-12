from __future__ import unicode_literals, division, absolute_import
import re
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.task import Task
from flexget.utils import requests
from flexget.utils.soup import get_soup
from bs4 import BeautifulSoup, NavigableString, Tag

log = logging.getLogger('serienjunkies')

reSingleEp  = re.compile(r'(S\d+E\d\d+)(?!-E)', re.I)
reMultiEp   = re.compile(r'(?P<season>S\d\d)E(?P<startep>\d\d+)-E?(?P<stopep>\d\d+)', re.I)
reSeason    = re.compile(r'(?<=\.|\-)S\d\d(?:[-\.]S\d\d)*(?!E\d\d+)', re.I)

reLanguage  = re.compile(r'Sprache')

reGerman    = re.compile(r'german|deutsch', re.I)
reForeign   = re.compile(r'englisc?h|französisch|japanisch|dänisch|norwegisch|niederländisch|ungarisch|italienisch|portugiesisch', re.I)
reSubtitle  = re.compile(r'Untertitel|Subs?|UT', re.I)


LANGUAGE = ['german', 'foreign', 'subtitle', 'dual']
HOSTER   = ['ul', 'cz', 'so', 'all']

DEFAULT_LANGUAGE = 'dual'
DEFAULT_HOSTER = 'ul'


class UrlRewriteSerienjunkies(object):

    """
    Serienjunkies urlrewriter
    Version 1.0.1

    Language setting works like a whitelist, the selected is needed,
    but others are still possible.

    Configuration
    language: [german|foreign|subtitle|dual] default "foreign"
    hoster: [ul|cz|so|all] default "ul"
    """

    schema = {
        'type': 'object',
        'properties': {
            'language': {'type': 'string', 'enum': LANGUAGE},
            'hoster': {'type': 'string', 'enum': HOSTER}
        },
        'additionalProperties': False
    }


    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.serienjunkies.org/') or url.startswith('http://serienjunkies.org/'):
            return True
        return False


    # urlrewriter API
    def url_rewrite(self, task, entry):
        series_url   = entry['url']
        search_title = re.sub('\[.*\] ', '', entry['title'])

        self.config = task.config.get('serienjunkies') or {}
        self.config.setdefault('hoster', DEFAULT_HOSTER)
        self.config.setdefault('language', DEFAULT_LANGUAGE)

        download_urls = self.parse_downloads(series_url, search_title)
        if not download_urls:
             entry.reject('No Episode found')
        else:
            entry['url'] = download_urls[-1]
            entry['description'] = ", ".join(download_urls)
            
        #Debug Information
        log.debug('TV Show URL: %s' % series_url)
        log.debug('Episode: %s' % search_title)
        log.debug('Download URL: %s' % download_urls)


    @plugin.internet(log)
    def parse_downloads(self, series_url, search_title):
        page = requests.get(series_url).content
        try:
            pageSoup = get_soup(page)
        except Exception as e:
            raise UrlRewritingError(e)
            
        urls = []
        # find all titles
        episode_titles = self.find_all_titles(search_title)
        if not episode_titles:
            raise UrlRewritingError('Unable to find episode')
        
        for ep_title in episode_titles:
            # find matching download
            episode_title = pageSoup.find('strong', text=re.compile(ep_title, re.I))
            if not episode_title:
                continue
                
            # find download container
            episode = episode_title.parent
            if not episode:
                continue

            # find episode language
            episode_lang = episode.find_previous('strong', text=re.compile('Sprache')).next_sibling
            if not episode_lang:
                continue

            # filter language
            if not self.check_language(episode_lang):
                continue

            # find download links
            links = episode.find_all('a')
            if not links:
                continue

            for link in links:
                if not link.has_attr('href'):
                    continue

                url = link['href']
                pattern = 'http:\/\/download\.serienjunkies\.org.*%s_.*\.html' % self.config['hoster']

                if re.match(pattern, url) or self.config['hoster'] == 'all':
                    urls.append(url)
                else:
                    continue
        return urls

    def find_all_titles(self,search_title):
        search_titles = []
        # Check type
        if reMultiEp.search(search_title):
            log.debug('Title seems to describe multiple episodes')
            first_ep = int(reMultiEp.search(search_title).group('startep'))
            last_ep = int(reMultiEp.search(search_title).group('stopep'))
            season = reMultiEp.search(search_title).group('season') + 'E'
            for i in range(first_ep,last_ep + 1):
                # ToDO: Umlaute , Mehrzeilig etc.
                search_titles.append(reMultiEp.sub(season + str(i).zfill(2) + '[\\\\w\\\\.\\\\(\\\\)]*',search_title))
        elif reSeason.search(search_title):
            log.debug('Title seems to describe one or more season')
            sString = reSeason.search(search_title).group(0)
            for s in re.findall('(?<!\-)S\d\d(?!\-)',sString):
                search_titles.append(reSeason.sub(s + '[\\\\w\\\\.]*',search_title))
            for s in re.finditer('(?<!\-)S(\d\d)-S(\d\d)(?!\-)',sString):
                sStart = int(s.group(1))
                sEnd = int(s.group(2))
                for i in range(sStart,sEnd+1):
                    search_titles.append(reSeason.sub('S' + str(i).zfill(2) + '[\\\\w\\\\.]*',search_title))
        else: 
            log.debug('Title seems to describe a single episode')
            search_titles.append(re.escape(search_title))
        return search_titles


    def check_language(self, language):
        # Cut additional Subtitles
        try:
            language =  language[:language.index("+")]
        except:
            pass

        languageList = re.split(r'[,&]', language)

        try:
            if   self.config['language'] == 'german':
                if reGerman.search(languageList[0]):               
                    return True
            elif self.config['language'] == 'foreign':
                if (reForeign.search(languageList[0]) and not languageList[1]) or \
                   (languageList[1] and not reSubtitle.search(languageList[1])):
                    return True
            elif self.config['language'] == 'subtitle':
                if languageList[1] and reSubtitle.search(languageList[1]): 
                    return True
            elif self.config['language'] == 'dual':
                if languageList[1] and not reSubtitle.search(languageList[1]):
                    return True
        except:
            pass
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteSerienjunkies, 'serienjunkies', groups=['urlrewriter'], api_ver=2)
