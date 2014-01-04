from __future__ import unicode_literals, division, absolute_import
import re
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup

log = logging.getLogger('serienjunkies')

LANGUAGE = ['de', 'en', 'both']
HOSTER = ['ul', 'cz', 'so']


class UrlRewriteSerienjunkies(object):

    """
    Serienjunkies urlrewriter
    Version 1.0.0

    Language setting works like a whitelist, the selected is needed,
    but others are still possible.

    Configuration
    language: [de|en|both] default "en"
    hoster: [ul|cz|so] default "ul"
    """

    schema = {
        'type': 'object',
        'properties': {
            'language': {'type': 'string', 'enum': LANGUAGE, 'default': 'en'},
            'hoster': {'type': 'string', 'enum': HOSTER, 'default': 'ul'}
        },
        'additionalProperties': False
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://download.serienjunkies.org/'):
            return False
        if url.startswith('http://www.serienjunkies.org/') or url.startswith('http://serienjunkies.org/'):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        series_url = entry['url']
        download_title = entry['title']
        search_title = re.sub('\[.*\] ', '', download_title)
        self.config = task.config.get('serienjunkies')
        download_url = self.parse_download(series_url, search_title, self.config, entry)
        log.debug('TV Show URL: %s' % series_url)
        log.debug('Episode: %s' % search_title)
        log.debug('Download URL: %s' % download_url)
        entry['url'] = download_url

    @plugin.internet(log)
    def parse_download(self, series_url, search_title, config, entry):
        page = requests.get(series_url).content
        try:
            soup = get_soup(page)
        except Exception as e:
            raise UrlRewritingError(e)

        config = config or {}
        config.setdefault('hoster', 'ul')
        config.setdefault('language', 'en')

        # find matching download
        episode_title = soup.find('strong', text=search_title)
        if not episode_title:
            raise UrlRewritingError('Unable to find episode')

        # find download container
        episode = episode_title.parent
        if not episode:
            raise UrlRewritingError('Unable to find episode container')

        # find episode language
        episode_lang = episode.find_previous('strong', text=re.compile('Sprache')).next_sibling
        if not episode_lang:
            raise UrlRewritingError('Unable to find episode language')

        # filter language
        if config['language'] in ['de', 'both']:
            if not re.search('german|deutsch', episode_lang, flags=re.IGNORECASE):
                entry.reject('Language does not match')
        if config['language'] in ['en', 'both']:
            if not re.search('englisc?h', episode_lang, flags=re.IGNORECASE):
                entry.reject('Language does not match')

        # find download links
        links = episode.find_all('a')
        if not links:
            raise UrlRewritingError('Unable to find download links')

        for link in links:
            if not link.has_attr('href'):
                continue

            url = link['href']
            pattern = 'http:\/\/download\.serienjunkies\.org.*%s_.*\.html' % config['hoster']

            if re.match(pattern, url):
                return url
            else:
                log.debug('Hoster does not match')
                continue


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteSerienjunkies, 'serienjunkies', groups=['urlrewriter'], api_ver=2)
