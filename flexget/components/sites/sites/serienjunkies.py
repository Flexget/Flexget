# coding=utf-8


import re

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.config_schema import one_or_more

logger = logger.bind(name='serienjunkies')

regex_single_ep = re.compile(r'(S\d+E\d\d+)(?!-E)', re.I)
regex_multi_ep = re.compile(r'(?P<season>S\d\d)E(?P<startep>\d\d+)-E?(?P<stopep>\d\d+)', re.I)
regex_season = re.compile(r'(?<=\.|\-)S\d\d(?:[-\.]S\d\d)*(?!E\d\d+)', re.I)

regex_language_container = re.compile(r'Sprache')

regex_is_german = re.compile(r'german|deutsch', re.I)
regex_is_foreign = re.compile(
    r'englisc?h|französisch|japanisch|dänisch|norwegisch|niederländisch|ungarisch|italienisch|portugiesisch',
    re.I,
)
regex_is_subtitle = re.compile(r'Untertitel|Subs?|UT', re.I)

LANGUAGE = ['german', 'foreign', 'subtitle', 'dual']
HOSTER = ['ul', 'so', '1fichier', 'ddl', 'filefactory', 'filer', 'nitroflare', 'oboom', 'rapidgator', 'turbobit',
          'uploaded', 'share-online', 'all']

DEFAULT_LANGUAGE = 'dual'
DEFAULT_HOSTER = 'uploaded'

HOSTER_MAP = {
    '1fichier': ['1fichier.com'],
    'ddl': ['ddl.to'],
    'filefactory': ['filefactory.com'],
    'filer': ['filer.net'],
    'nitroflare': ['nitroflare.com'],
    'oboom': ['oboom.com'],
    'rapidgator': ['rapidgator.net'],
    'turbobit': ['turbobit.net'],
    'uploaded': ['uploaded.to', 'uploaded.net'],
    'share-online': ['share-online.to']
}


class SerienjunkiesMatch:
    def __init__(self):
        self.hoster = None
        self.quality = float("inf")
        self.found = False

    @classmethod
    def factory(cls, href, next_sibling, hoster_config):
        instance = cls()
        if isinstance(hoster_config, str):
            if hoster_config == 'all' or cls.does_match(href, next_sibling, hoster_config):
                instance.hoster = hoster_config
                instance.quality = 0
                instance.found = True
            else:
                instance.quality = float("inf")
        else:
            for quality, hoster in enumerate(hoster_config):
                if cls.does_match(href, next_sibling, hoster):
                    instance.hoster = hoster
                    instance.quality = quality
                    instance.found = True
                    break

            if not instance.found and 'all' in hoster_config:
                instance.hoster = 'all'
                instance.quality = hoster_config.index('all')
                instance.found = True
        return instance

    @staticmethod
    def does_match(href, next_sibling, hoster):
        match_found = False
        if hoster == 'ul':
            hoster = 'uploaded'
        if hoster == 'so':
            hoster = 'share-online'

        if hoster in ['uploaded', 'share-online']:
            if hoster == 'uploaded':
                url_tag = 'ul'
            if hoster == 'share-online':
                url_tag = 'so'
            pattern = (
                    r'http:\/\/download\.serienjunkies\.org.*%s_.*\.html' % url_tag
            )

            if re.match(pattern, href):
                match_found = True

        if not match_found and hoster in HOSTER_MAP and next_sibling in HOSTER_MAP[hoster]:
            match_found = True

        return match_found


class UrlRewriteSerienjunkies:
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
            'hoster': one_or_more({'type': 'string', 'enum': HOSTER}),
            'season_pack_fallback': {'type': 'boolean', 'default': True}
        },
        'additionalProperties': False,
    }

    # Since the urlrewriter relies on a config, we need to create a default one
    config = {'hoster': DEFAULT_HOSTER, 'language': DEFAULT_LANGUAGE}

    def on_task_start(self, task, config):
        self.config = config

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.serienjunkies.org/') or url.startswith(
                'http://serienjunkies.org/'
        ):
            return True
        return False

    # urlrewriter API
    def url_rewrite(self, task, entry):
        series_url = entry['url']
        search_title = re.sub(r'\[.*\] ', '', entry['title'])

        download_urls = self.parse_downloads(series_url, search_title, self.config.get('season_pack_fallback', False))
        if not download_urls:
            entry.reject('No Episode found')
        else:
            entry['url'] = download_urls[-1]
            entry['description'] = ", ".join(download_urls)

        # Debug Information
        logger.debug('TV Show URL: {}', series_url)
        logger.debug('Episode: {}', search_title)
        logger.debug('Download URL: {}', download_urls)

    @plugin.internet(logger)
    def parse_downloads(self, series_url, search_title, season_pack_fallback):
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

            urls = self.find_urls(urls, episode_title)

        if len(urls) == 0 and season_pack_fallback:
            episode_match_pattern = re.compile('\.S(\d*)E(\d*)\.')
            season_title_match = re.search(episode_match_pattern, search_title)
            if season_title_match:
                season_title = re.sub(episode_match_pattern, r'.S\1.', search_title)
                season_titles = self.find_all_titles(season_title)
                if not season_titles:
                    raise UrlRewritingError('Unable to find season')

                for se_title in season_titles:
                    # find matching download
                    season_title = soup.find('strong', text=re.compile(se_title, re.I))
                    if not season_title:
                        continue

                    urls = self.find_urls(urls, season_title)

        return urls

    def find_urls(self, urls, episode_title):
        # find download container
        episode = episode_title.parent
        do_exit = False
        if not episode:
            do_exit = True

        if not do_exit:
            # find episode language
            episode_lang = episode.find_previous('strong', text=re.compile('Sprache')).next_sibling
            if not episode_lang:
                logger.warning('No language found for: {}', episode_lang)
                do_exit = True

        if not do_exit:
            # filter language
            if not self.check_language(episode_lang):
                logger.warning(
                    'languages not matching: {} <> {}', self.config.get('language'), episode_lang
                )
                do_exit = True

        if not do_exit:
            # find download links
            links = episode.find_all('a')
            if not links:
                logger.warning('No links found for: {}', episode_title)
                do_exit = True

        best_hoster_match = None

        if not do_exit:
            for link in links:
                if not link.has_attr('href'):
                    continue

                url = link['href']
                next_sibling = str(link.next_sibling).strip(" |")
                match = SerienjunkiesMatch.factory(url, next_sibling, self.config.get('hoster', 'all'))

                if match.found:
                    if best_hoster_match is None:
                        best_hoster_match = match
                    elif best_hoster_match.hoster != match.hoster \
                            and match.quality < best_hoster_match.quality:
                        urls = []
                        best_hoster_match = match
                    elif best_hoster_match.hoster != match.hoster \
                            and match.quality > best_hoster_match.quality:
                        continue

                    urls.append(url)
                else:
                    continue

        return urls

    def find_all_titles(self, search_title):
        search_titles = []
        # Check type
        if regex_multi_ep.search(search_title):
            logger.debug('Title seems to describe multiple episodes')
            first_ep = int(regex_multi_ep.search(search_title).group('startep'))
            last_ep = int(regex_multi_ep.search(search_title).group('stopep'))
            season = regex_multi_ep.search(search_title).group('season') + 'E'
            for i in range(first_ep, last_ep + 1):
                # ToDO: Umlaute , Mehrzeilig etc.
                search_titles.append(
                    regex_multi_ep.sub(
                        season + str(i).zfill(2) + '[\\\\w\\\\.\\\\(\\\\)]*', search_title
                    )
                )
        elif regex_season.search(search_title):
            logger.debug('Title seems to describe one or more season')
            search_string = regex_season.search(search_title).group(0)
            for s in re.findall(r'(?<!\-)S\d\d(?!\-)', search_string):
                search_titles.append(regex_season.sub(s + '[\\\\w\\\\.]*', search_title))
            for s in re.finditer(r'(?<!\-)S(\d\d)-S(\d\d)(?!\-)', search_string):
                season_start = int(s.group(1))
                season_end = int(s.group(2))
                for i in range(season_start, season_end + 1):
                    search_titles.append(
                        regex_season.sub('S' + str(i).zfill(2) + '[\\\\w\\\\.]*', search_title)
                    )
        else:
            logger.debug('Title seems to describe a single episode')
            search_titles.append(re.escape(search_title))
        return search_titles

    def check_language(self, languages):
        # Cut additional Subtitles
        languages = languages.split('|', 1)[0]

        language_list = re.split(r'[,&]', languages)

        configured_language = self.config.get('language')

        if configured_language is None:
            return True

        try:
            if configured_language == 'german':
                if regex_is_german.search(language_list[0]):
                    return True
            elif configured_language == 'foreign':
                if (regex_is_foreign.search(language_list[0]) and len(language_list) == 1) or (
                        len(language_list) > 1 and not regex_is_subtitle.search(language_list[1])
                ):
                    return True
            elif configured_language == 'subtitle':
                if len(language_list) > 1 and regex_is_subtitle.search(language_list[1]):
                    return True
            elif configured_language == 'dual':
                if len(language_list) > 1 and not regex_is_subtitle.search(language_list[1]):
                    return True
        except (KeyError, re.error):
            pass

        return False


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteSerienjunkies, 'serienjunkies', interfaces=['urlrewriter', 'task'], api_ver=2
    )
