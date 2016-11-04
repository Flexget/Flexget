# coding=utf-8
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import re
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup

log = logging.getLogger('serienjunkies')

regex_single_ep = re.compile(r'(S\d+E\d\d+)(?!-E)', re.I)
regex_multi_ep = re.compile(r'(?P<season>S\d\d)E(?P<startep>\d\d+)-E?(?P<stopep>\d\d+)', re.I)
regex_season = re.compile(r'(?<=\.|\-)S\d\d(?:[-\.]S\d\d)*(?!E\d\d+)', re.I)

regex_language_container = re.compile(r'Sprache')

regex_is_german = re.compile(r'german|deutsch', re.I)
regex_is_foreign = re.compile(
    r'englisc?h|französisch|japanisch|dänisch|norwegisch|niederländisch|ungarisch|italienisch|portugiesisch', re.I)
regex_is_subtitle = re.compile(r'Untertitel|Subs?|UT', re.I)

LANGUAGE = ['german', 'foreign', 'subtitle', 'dual']
HOSTER = ['ul', 'cz', 'so', 'all']

DEFAULT_LANGUAGE = 'dual'
DEFAULT_HOSTER = 'ul'


class UrlRewriteSerienjunkies(object):
    """
    Serienjunkies urlrewriter
    Version 1.0.2

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
        series_url = entry['url']
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

        # Debug Information
        log.debug('TV Show URL: %s', series_url)
        log.debug('Episode: %s', search_title)
        log.debug('Download URL: %s', download_urls)

    @plugin.internet(log)
    def parse_downloads(self, series_url, search_title):
        page = requests.get(series_url).content
        try:
            soup = get_soup(page)
        except Exception as e:
            raise UrlRewritingError(e)

        urls = []
        # find all titles
        episode_titles = self.find_all_titles(search_title)
        if not episode_titles:
            raise UrlRewritingError('Unable to find episode')

        for ep_title in episode_titles:
            # find matching download
            episode_title = soup.find('strong', text=re.compile(ep_title, re.I))
            if not episode_title:
                continue

            # find download container
            episode = episode_title.parent
            if not episode:
                continue

            # find episode language
            episode_lang = episode.find_previous('strong', text=re.compile('Sprache')).next_sibling
            if not episode_lang:
                log.warning('No language found for: %s', series_url)
                continue

            # filter language
            if not self.check_language(episode_lang):
                log.warning('languages not matching: %s <> %s', self.config['language'], episode_lang)
                continue

            # find download links
            links = episode.find_all('a')
            if not links:
                log.warning('No links found for: %s', series_url)
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

    def find_all_titles(self, search_title):
        search_titles = []
        # Check type
        if regex_multi_ep.search(search_title):
            log.debug('Title seems to describe multiple episodes')
            first_ep = int(regex_multi_ep.search(search_title).group('startep'))
            last_ep = int(regex_multi_ep.search(search_title).group('stopep'))
            season = regex_multi_ep.search(search_title).group('season') + 'E'
            for i in range(first_ep, last_ep + 1):
                # ToDO: Umlaute , Mehrzeilig etc.
                search_titles.append(regex_multi_ep.sub(season + str(i).zfill(2) + '[\\\\w\\\\.\\\\(\\\\)]*',
                                                        search_title))
        elif regex_season.search(search_title):
            log.debug('Title seems to describe one or more season')
            search_string = regex_season.search(search_title).group(0)
            for s in re.findall('(?<!\-)S\d\d(?!\-)', search_string):
                search_titles.append(regex_season.sub(s + '[\\\\w\\\\.]*', search_title))
            for s in re.finditer('(?<!\-)S(\d\d)-S(\d\d)(?!\-)', search_string):
                season_start = int(s.group(1))
                season_end = int(s.group(2))
                for i in range(season_start, season_end + 1):
                    search_titles.append(regex_season.sub('S' + str(i).zfill(2) + '[\\\\w\\\\.]*', search_title))
        else:
            log.debug('Title seems to describe a single episode')
            search_titles.append(re.escape(search_title))
        return search_titles

    def check_language(self, languages):
        # Cut additional Subtitles
        languages = languages.split('|', 1)[0]

        language_list = re.split(r'[,&]', languages)

        try:
            if self.config['language'] == 'german':
                if regex_is_german.search(language_list[0]):
                    return True
            elif self.config['language'] == 'foreign':
                if (regex_is_foreign.search(language_list[0]) and len(language_list) == 1) or \
                        (len(language_list) > 1 and not regex_is_subtitle.search(language_list[1])):
                    return True
            elif self.config['language'] == 'subtitle':
                if len(language_list) > 1 and regex_is_subtitle.search(language_list[1]):
                    return True
            elif self.config['language'] == 'dual':
                if len(language_list) > 1 and not regex_is_subtitle.search(language_list[1]):
                    return True
        except (KeyError, re.error):
            pass

        return False


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteSerienjunkies, 'serienjunkies', groups=['urlrewriter'], api_ver=2)
