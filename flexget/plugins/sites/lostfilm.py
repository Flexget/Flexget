# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

__author__ = 'duhast, danfocus'

log = logging.getLogger('lostfilm')

NEW_RELEASES_URL = 'http://www.lostfilm.tv/new'
V_SEARCH_URL = 'http://www.lostfilm.tv/v_search.php'
QUALITY_MAP = {
    'SD': ('480p', 'avi'),
    '1080': ('1080p', 'mkv'),
    'MP4': ('720p', 'mp4'),
    'HD': ('720p', 'mkv')
}

class LostFilm(object):
    """
    Fetches new LostFilm.TV releases

    Example::

      lostfilm: yes

    Advanced usage:

      lostfilm:
        url: <url>
        favourites_only: <bool>
        pages: <number>
    """

    schema = {
        'type': ['boolean', 'object'],
        'properties': {
            'url': {'type': 'string', 'format': 'url', 'default': NEW_RELEASES_URL},
            'favourites_only': {'type': 'boolean', 'default': False},
            'pages': {'type': 'integer', 'minimum': 1, 'default': 1}
        },
        'additionalProperties': False
    }

    def prepare_config(self, config):
        """Set default url and pages config"""
        if isinstance(config, bool) and config is True:
            config = {'url': NEW_RELEASES_URL, 'pages': 1, 'favourites_only': False}
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if config is False:
            return

        release_type = 99 if config['favourites_only'] else 0

        entries = []
        for page_num in range(1, config['pages']+1):
            # Fetch release page
            release_url = '{:s}/page_{:d}/type_{:d}'.format(config['url'], page_num, release_type)
            log.debug('Fetching page %d of %d', page_num, config['pages'])
            try:
                response = task.requests.get(release_url)
            except RequestException as e:
                raise PluginError('Could not fetch new releases page: %s'.format(e))

            try:
                index_page = get_soup(response.content)
            except:
                raise PluginError('Cannot parse new releases page')
            # Iterate over releases
            seen_buttons = index_page.find_all('div', 'haveseen-btn')
            for seen_btn in seen_buttons:
                try:
                    details_pane = seen_btn.parent.find('div', 'details-pane')

                    episode_name_rus = details_pane.find('div', 'alpha').text.strip()
                    episode_name_eng = details_pane.find('div', 'beta').text.strip()
                    series_name_rus = details_pane.parent.find('div', 'name-ru').text.strip()
                    series_name_eng = details_pane.parent.find('div', 'name-en').text.strip()
                    lostfilm_num, season_num, episode_num = [int(x) for x in seen_btn['data-code'].split('-')]
                except AttributeError:
                    log.exception('Could not parse %s, probably HTML markup was changed', release_url)
                    continue

                params = {'c': lostfilm_num, 's': season_num, 'e': episode_num}
                redirect_url = V_SEARCH_URL
                try:
                    response = task.requests.get(redirect_url, params=params)
                except RequestException as e:
                    log.error('Could not connect to redirect url: %s', e)
                    continue

                page = get_soup(response.content)
                try:
                    redirect_url = page.head.meta['content'].split('url=')[1]  # retre.org
                except:
                    log.error('Missing redirect')
                    continue

                try:
                    response = task.requests.get(redirect_url)
                except RequestException as e:
                    log.error('Could not connect to RETRE redirect url: %s', e)
                    continue

                page = get_soup(response.content)

                episode_id = 'S{:02d}E{:02d}'.format(season_num, episode_num)
                for item in page.findAll('div', 'inner-box--item'):
                    torrent_link = quality = None
                    try:
                        torrent_link = item.find('div', 'inner-box--link sub').a['href']  # http://tracktor.in/...
                        quality = item.find('div', 'inner-box--label').text.strip()
                    except:
                        log.debug('Item doesn\'t have a link or quality')
                        continue
                    if torrent_link is None or quality is None:
                        log.debug('Item doesn\'t have a link or quality')
                        continue
                    if QUALITY_MAP.get(quality):
                        quality, file_ext = QUALITY_MAP.get(quality)
                    else:
                        file_ext = 'avi'
                    if series_name_eng:
                        title_parts = [series_name_eng, episode_id, quality, 'rus.LostFilm.TV', file_ext, 'torrent']
                        new_title = '.'.join(title_parts).replace(' ', '.')
                    else:
                        if item.get('title') is not None:
                            new_title = '{} {}'.format(item['title'], quality)
                        else:
                            log.debug('Item doesn\'t have a title')
                            continue

                    new_entry = Entry()
                    new_entry['url'] = torrent_link
                    new_entry['title'] = new_title.strip()
                    if series_name_rus:
                        new_entry['series_name_rus'] = series_name_rus
                    if episode_name_rus:
                        new_entry['episode_name_rus'] = episode_name_rus
                    if series_name_eng:
                        new_entry['series_name_eng'] = series_name_eng
                    if episode_name_eng:
                        new_entry['episode_name_eng'] = episode_name_eng
                    entries.append(new_entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(LostFilm, 'lostfilm', api_ver=2)
