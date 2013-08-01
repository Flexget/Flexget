import re
import logging
from plugin_urlrewriting import UrlRewritingError
from flexget.plugin import internet, register_plugin
from flexget.utils import requests
from flexget.utils.tools import urlopener
from flexget.utils.soup import get_soup
from flexget import validator

log = logging.getLogger('serienjunkies')

#configuration
hoster = 'ul'

class UrlRewriteSerienjunkies(object):
    """Serienjunkies urlrewriter."""

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
        download_url = self.parse_download(series_url, search_title)
        log.debug('TV Show URL: %s' % series_url)
        log.debug('Episode: %s' % search_title)
        log.debug('Download URL: %s' % download_url)
        entry['url'] = download_url

    @internet(log)
    def parse_download(self, series_url, search_title):
        page = requests.get(series_url).content
        try:
            soup = get_soup(page)
        except Exception, e:
            raise UrlRewritingError(e)

        #find matching download
        episode_title = soup.find('strong', text=search_title)
        if not episode_title:
            raise UrlRewritingError('Unable to find episode')

        #find download container
        episode = episode_title.parent
        if not episode:
            raise UrlRewritingError('Unable to find episode container')

        #find download links
        links = episode.find_all('a')
        if not links:
            raise UrlRewritingError('Unable to find download links')

        for link in links:
            if not link.has_attr('href'):
                continue

            url = link['href']
            pattern = 'http:\/\/download\.serienjunkies\.org.*%s_.*\.html' % hoster

            if re.match(pattern, url):
                return url
            else:
                log.debug('Hoster does not match')
                continue

register_plugin(UrlRewriteSerienjunkies, 'serienjunkies', groups=['urlrewriter'])
