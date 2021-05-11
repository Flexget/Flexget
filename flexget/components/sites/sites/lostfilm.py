# -*- coding: utf-8 -*-


import re

import feedparser
from urllib.request import ProxyHandler
from loguru import logger

from flexget import entry, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup
from flexget.utils import qualities
from flexget.components.sites.utils import normalize_unicode

__authors__ = 'danfocus, Karlson2k'

logger = logger.bind(name='lostfilm')

RSS_TITLE_REGEXP = re.compile(r'^(?P<sr_rus>[^)(]+?)(?: \((?P<sr_org>[^)]+)\))?\. (?:(?P<ep_rus>.*)\. )?\(S(?P<season>\d+)E(?P<episode>\d+)\)$')
RSS_LINK_REGEXP = re.compile(r'^https?://[a-z./]+/series/(?P<sr_org2>.+)/season_(?P<season>\d+)/episode_(?P<episode>\d+)/$')
RSS_LF_ID_REGEXP = re.compile(r'/Images/(?P<id>\d+)/Posters/image\.(?:png|jpg|jpeg)')
PAGE_TEXT_REGEXP = re.compile(r'^\s*(?P<season>\d+)\s+сезон\s+(?P<episode>\d+)\s+серия\.(?:\s(?P<ep_rus>[^(]+?(?:\([^)]+?\))??))?(?:\s+\((?P<ep_org>[^)(]*?(?:\([^)]+?\))??)\s?\))?$')
PAGE_LINKMAIN_REGEXP = re.compile(r'(?:(?P<sr_rus>.+?)\.\s+)??(?:(?P<season>\d+) сезон, (?P<episode>\d+) серия\.\s+)?(?:(?P<ql>[0-9A-Za-z]+)\s)?(?P<tp>\b[A-Za-z-]*(?:Rip|RIP|rip))$')

quality_map = {
    'SD': '480p.mp3.xvid',
    '1080': '1080p.ac3.h264',
    'MP4': '720p.aac.h264',
    'HD': '720p.ac3.h264',
}

LOSTFILM_URL = 'https://lostfilm.tv/rss.xml'

SIMPLIFY_MAP = str.maketrans({
    '&': ' and ',
    "'": None,
    '\\': None,
})
SIMPLIFY_MAP.update(dict.fromkeys([ord(ch) for ch in '_./-,[](){}:;!?@#%^*+<>=~`$'], ' '))

class TextProcessingError(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return repr(self.value)


class LostFilm:
    """
    Grab new torrents from lostfilm RSS feed

    Example:

      lostfilm: yes

    or

      lostfilm: <lf_session_cookie_value>

    Advanced usage:

      lostfilm:
        url: <url>
        lf_session: <lf_session_cookie_value>
        prefilter: no
    """

    schema = {
        'type': ['boolean', 'string', 'object'],
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'lf_session': {'type': 'string'},
            'prefilter': {'type': 'boolean'},
         },
        'additionalProperties': False,
    }

    def build_config(self, config):
        """Set defaults to config"""
        cfg = dict()
        if isinstance(config, bool):
            cfg['enabled'] = bool(config)
        elif isinstance(config, str):
            cfg['lf_session'] = str(config)
            cfg['enabled'] = True
        else:
            cfg = dict(config)
            cfg['enabled'] = True
        cfg.setdefault('url', LOSTFILM_URL)
        cfg.setdefault('prefilter', True)
        return cfg

    def on_task_input(self, task, config):
        config = self.build_config(config)
        if not config['enabled']:
            return
        if config.get('lf_session') is not None:
            task.requests.cookies.set('lf_session', config['lf_session'])
            logger.debug('lf_session is set')
        prefilter_list = set()
        if config['prefilter']:
            prefilter_list = self._get_series(task)
            if prefilter_list:
                logger.verbose('Generated pre-filter list with {} entries', len(prefilter_list))
            else:
                logger.info('Pre-filter list is empty. No series names are configured?')

        proxy_handler = None
        if task.requests.proxies is not None:
            proxy_handler = ProxyHandler(task.requests.proxies)
        try:
            rss = feedparser.parse(config['url'], handlers=[proxy_handler])
        except Exception:
            raise PluginError('Cannot parse rss feed')
        status = rss.get('status')
        if status != 200:
            raise PluginError('Received %s status instead of 200 (OK)' % status)
        entries = []
        for idx, item in enumerate(rss.entries, 1):
            series_name_rus = series_name_org = None
            episode_name_rus = episode_name_org = None
            season_num = episode_num = None
            perfect_match = False

            if item.get('title') is None:
                logger.warning('RSS item doesn\'t have a title')
            else:
                logger.trace('Got RSS item title: {}', item['title'])
                title_match = RSS_TITLE_REGEXP.fullmatch(item['title'])
                if title_match is not None:
                    if title_match['sr_org'] is not None:
                        series_name_org = title_match['sr_org']
                        series_name_rus = title_match['sr_rus']
                        if title_match['ep_rus'] is not None:
                            perfect_match = True
                    else:
                        series_name_org = title_match['sr_rus']
                        series_name_rus = None
                    season_num = int(title_match['season'])
                    episode_num = int(title_match['episode'])
                    episode_name_rus = title_match['ep_rus']
                else:
                    logger.warning('Cannot parse RSS item title: {}', item['title'])

            # Skip series names that are not configured.
            # Do not filter out the current item if it is not matched perfectly.
            # It's better to process an extra item which will be filtered later by
            # series plugin than throw out actually needed item because incorrectly
            # matched name was not found in the pre-filter list.
            if prefilter_list:
                if perfect_match:
                    try:
                        folded_name = self._simplify_name(series_name_org)
                    except TextProcessingError as e:
                        logger.warning('RSS item series name "{}" could be wrong', series_name_org)
                        folded_name = None
                    if folded_name and folded_name not in prefilter_list:
                        if idx != len(rss.entries) or entries or task.no_entries_ok:
                            logger.debug('Skipping "{}" as "{}" was not found in the list of configured series',
                                     item['title'], series_name_org)
                            continue
                        else:
                            logger.debug('Force adding the last RSS item to the result to avoid warning of empty output')
                    else:
                        logger.trace('"{}" was foung in the list of configured series', series_name_org)
                else:
                    logger.trace('Not skipping RSS item as series names may be detected incorrectly')

            if item.get('description') is None:
                logger.warning('RSS item doesn\'t have a description, skipping')
                continue
            lostfilm_id_match = RSS_LF_ID_REGEXP.search(item['description'])
            if lostfilm_id_match is None or lostfilm_id_match['id'] is None:
                logger.warning('RSS item doesn\'t have lostfilm id in the description: {}, skipping'. item['description'])
                continue
            lostfilm_id = int(lostfilm_id_match['id'])

            if not series_name_org or season_num is None or episode_num is None:
                if item.get('link') is None:
                    logger.warning('RSS item doesn\'t have a link, skipping')
                    continue
                link_match = RSS_LINK_REGEXP.fullmatch(item['link'])
                if link_match is None:
                    logger.warning('Cannot parse RSS item link, skipping: {}', item['link'])
                    continue
                series_name_org = link_match['sr_org2'].replace('_', ' ')
                season_num = int(link_match['season'])
                episode_num = int(link_match['episode'])
                logger.verbose('Using imprecise information from RSS item link')

            logger.trace(('Processing RSS entry: names: series "{}", series ru "{}", episode ru "{}"; '
                          'numbers: season "{}", episode "{}", lostfilm id "{}"; perfect detect: {}'),
                           series_name_org, series_name_rus, episode_name_rus,
                           season_num, episode_num, lostfilm_id, perfect_match)
            params = {'c': lostfilm_id, 's': season_num, 'e': episode_num}
            redirect_url = 'https://www.lostfilm.tv/v_search.php'
            try:
                response = task.requests.get(redirect_url, params=params)
            except RequestException as e:
                logger.error('Failed to get lostfilm download page: {:s}'.format(e))
                continue

            if response.status_code != 200:
                if config.get('lf_session') is not None:
                    logger.error('Got status {} while retriving lostfilm.tv torrent download page. ' \
                                 'Check whether "lf_session" parameter is correct.', response.status_code)
                else:
                    logger.error('Got status {} while retriving lostfilm.tv torrent download page. ' \
                                 'Specify your "lf_session" cookie value in plugin parameters.', response.status_code)
                continue

            page = get_soup(response.content)

            redirect_url = None
            find_item = page.find('html', recursive=False)
            if find_item is not None:
                find_item = find_item.find('head', recursive=False)
                if find_item is not None:
                    find_item = find_item.find('meta', attrs={'http-equiv': "refresh"}, recursive=False)
                    if find_item is not None and find_item.has_attr('content') and find_item['content'].startswith('0; url=http'):
                        redirect_url = find_item['content'][7:]
            if not redirect_url:
                if config.get('lf_session') is not None:
                    logger.error('Links were not foung on lostfilm.tv torrent download page. ' \
                                 'Check whether "lf_session" parameter is correct.')
                else:
                    logger.error('Links were not foung on lostfilm.tv torrent download page. ' \
                                 'Specify your "lf_session" cookie value in plugin parameters.')
                continue

            try:
                response = task.requests.get(redirect_url)
            except RequestException as e:
                logger.error('Could not connect to redirect url2: {:s}', e)
                continue

            page = get_soup(response.content)

            if not perfect_match:
                logger.trace('Trying to find series names in the final torrents download page')
                find_item = page.find('div', class_='inner-box--subtitle')
                if find_item is not None:
                    title_org_div = find_item.text.strip()
                    if title_org_div.endswith(', сериал') and len(title_org_div) != 8:
                        series_name_org = title_org_div[:-8]
                    else:
                        logger.verbose('Cannot parse text on the final download page for original series name')
                else:
                    logger.verbose('Cannot parse the final download page for original series name')

                find_item = page.find('div', class_='inner-box--title')
                if find_item is not None and \
                   find_item.text.strip():
                    series_name_rus = find_item.text.strip()
                else:
                    logger.verbose('Cannot parse the final download page for russian series name')

            find_item = page.find('div', class_='inner-box--text')
            if find_item is not None:
                info_match = PAGE_TEXT_REGEXP.fullmatch(find_item.text.strip())
                if info_match is not None:
                    if int(info_match['season']) != season_num or int(info_match['episode']) != episode_num:
                        logger.warning(('Using season number ({}) and episode number ({}) from download page instead of '
                                    'season number ({}) and episode number ({}) in RSS item'), int(info_match['season']),
                                    int(info_match['episode']), season_num, episode_num)
                        season_num = int(info_match['season'])
                        eposode_num = int(info_match['episode'])
                    if info_match['ep_org'] is not None:
                        episode_name_org = info_match['ep_org'].strip()
                    if not perfect_match and info_match['ep_rus'] is not None and \
                      info_match['ep_rus'].strip():
                        episode_name_rus = info_match['ep_rus'].strip()
                else:
                    logger.verbose('Cannot parse text on the final download page for episode names')
            else:
                logger.verbose('Cannot parse the final download page for episode names')

            r_type = ''
            find_item = page.find('div', class_='inner-box--link main')
            if find_item:
                find_item = find_item.find('a')
                if find_item:
                    info_match = PAGE_LINKMAIN_REGEXP.search(find_item.text)
                    if info_match:
                        r_type = info_match['tp']
                        logger.debug('Found rip type "{}"', r_type)

            if not series_name_org:
                find_item = item.get['title']
                if find_item:
                    logger.warning(('Unable to detect series name. Full RSS item title will be used in hope '
                                    'that series parser will be able to detect something: {}'),
                                    find_item)
                    series_name_org = None
                else:
                    logger.error('Unable to detect series name. Skipping RSS item.')
                    continue

            d_items = page.find_all('div', class_='inner-box--item')
            if not d_items:
                logger.error('No download links were found on the download page')
                continue

            episode_id = 'S{:02d}E{:02d}'.format(season_num, episode_num)
            for d_item in d_items:
                find_item = d_item.find('div', class_='inner-box--link sub').a['href']
                if not find_item:
                    logger.warning('Download item does not have a link')
                    continue
                torrent_link = find_item

                find_item = d_item.find('div', class_='inner-box--label')
                if not find_item:
                    logger.warning('Download item does not have quality indicator')
                    continue
                lf_quality = find_item.text.strip()

                if quality_map.get(lf_quality):
                    quality = quality_map.get(lf_quality)
                else:
                    logger.verbose('Download item has unknown quality indicator: {}', lf_quality)
                    quality = lf_quality
                if series_name_org:
                    new_title = '.'.join(
                        [
                            series_name_org,
                            episode_id,
                            quality,
                            r_type,
                            'LostFilm.TV'
                        ]
                    )
                else:
                    new_title = '{} {}'.format(item['title'], quality).strip()
                new_entry = Entry()
                new_entry['title'] = new_title
                new_entry['url'] = torrent_link
                if series_name_org:
                    new_entry['series_name'] = series_name_org
                    new_entry['series_name_org'] = series_name_org
                if perfect_match:
                    new_entry['series_exact'] = True
                new_entry['series_id'] = episode_id
                new_entry['series_id_type'] = 'ep'
                new_entry['series_season'] = season_num
                new_entry['series_episode'] = episode_num
                new_entry['series_episodes'] = 1
                new_entry['season_pack'] = None
                new_entry['proper'] = False
                new_entry['proper_count'] = 0
                new_entry['special'] = False
                new_entry['release_group'] = 'LostFilm.TV'
                if quality_map.get(lf_quality):
                    if r_type:
                        new_entry['quality'] = qualities.Quality('.'.join([quality, r_type]))
                    else:
                        new_entry['quality'] = qualities.Quality(quality)
                if series_name_rus:
                    new_entry['series_name_rus'] = series_name_rus
                if episode_name_rus:
                    new_entry['episode_name_rus'] = episode_name_rus
                if episode_name_org:
                    new_entry['episode_name_org'] = episode_name_org
                new_entry['lostfilm_id'] = lostfilm_id
                entries.append(new_entry)
                logger.trace(('Added new entry: names: series "{}", series ru "{}", episode "{}", episode ru "{}"; '
                        'numbers: season "{}", episode "{}", lostfilm id "{}"; quality: "{}", perfect detect: {}'),
                        series_name_org, series_name_rus, episode_name_org, episode_name_rus,
                        season_num, episode_num, lostfilm_id, quality, perfect_match)

        return entries


    @staticmethod
    def _simplify_name(name: str) -> str:
        name = normalize_unicode(name)
        name = name.replace('&amp;', ' and ').translate(SIMPLIFY_MAP)
        name = ' '.join(name.split()).casefold()
        if not name:
            raise TextProcessingError('Simplified name of series is empty')
        return name


    @staticmethod
    def _get_series(task):
        if not task.config.get('series'):
            logger.debug('No series plugin in the task')
            return None

        names_list = set()
        try:
            # build list of all configured series names
            if isinstance(task.config['series'], list):
                # Flat list
                LostFilm._add_names_from_cfg_list(names_list, task.config['series'])
            elif isinstance(task.config['series'], dict):
                # Dictionary with groups
                for group, series_list in task.config['series'].items():
                    if group == 'settings':
                        continue
                    LostFilm._add_names_from_cfg_list(names_list, series_list)
            else:
                logger.warning('Unsupported series configuration type')
                return None
        except Exception as e:
            logger.warning('Error parsing series config: {:s}'.format(repr(e)))
            names_list = None

        return names_list


    @staticmethod
    def _add_names_from_cfg_list(names_list: set, cfg_list: list) -> None:
        for s_item in cfg_list:
            if isinstance(s_item, str):
                names_list.add(LostFilm._simplify_name(s_item))
            elif isinstance(s_item, int) or isinstance(s_item, float):
                # The name is something like '365' or '36.6'
                names_list.add(LostFilm._simplify_name(str(s_item)))
            elif isinstance(s_item, dict):
                s_name, s_cfg = list(s_item.items())[0]
                names_list.add(LostFilm._simplify_name(s_name))
                if s_cfg.get('alternate_name'):
                    if isinstance(s_cfg['alternate_name'], str):
                        names_list.add(LostFilm._simplify_name(s_cfg['alternate_name']))
                    elif isinstance(s_cfg['alternate_name'], list):
                        # A list of alternate names
                        for a_name in s_cfg['alternate_name']:
                            names_list.add(LostFilm._simplify_name(a_name))
                    else:
                        raise PluginError('Cannot read series "alternate_name" for "{:s}"'.format(s_name))
            else:
                raise PluginError('Series configuration list item has ' \
                                  'unsupported type: %s' % type(s_item))


@event('plugin.register')
def register_plugin():
    plugin.register(LostFilm, 'lostfilm', api_ver=2)
