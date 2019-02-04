# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

__author__ = 'danfocus'

log = logging.getLogger('lostfilm')

EPISODE_REGEXP = re.compile(r'.*lostfilm.tv/series/.*/season_(\d+)/episode_(\d+)/.*')
LOSTFILM_ID_REGEXP = re.compile(r'.*static.lostfilm.tv/Images/(\d+)/Posters/.*')
TEXT_REGEXP = re.compile(r'^\d+\s+сезон\s+\d+\s+серия\.\s(.+)\s\((.+)\)$')

quality_map = {
    'SD': ('480p', 'avi'),
    '1080': ('1080p', 'mkv'),
    'MP4': ('720p', 'mp4'),
    'HD': ('720p', 'mkv'),
}

LOSTFILM_URL = 'http://lostfilm.tv/rss.xml'


class LostFilm(object):
    """
    Change new lostfilm's rss links

    Example::

      lostfilm: yes

    Advanced usage:

      lostfilm:
        url: <url>
    """

    schema = {
        'type': ['boolean', 'object'],
        'properties': {'url': {'type': 'string', 'format': 'url'}},
        'additionalProperties': False,
    }

    def build_config(self, config):
        """Set default url to config"""
        if isinstance(config, bool) and config is True:
            config = {'url': LOSTFILM_URL}
        return config

    def on_task_input(self, task, config):
        config = self.build_config(config)
        if config is False:
            return
        try:
            rss = feedparser.parse(config['url'])
        except Exception:
            raise PluginError('Cannot parse rss feed')
        if rss.get('status') != 200:
            raise PluginError('Received not 200 (OK) status')
        entries = []
        for item in rss.entries:
            if item.get('link') is None:
                log.debug('Item doesn\'t have a link')
                continue
            if item.get('description') is None:
                log.debug('Item doesn\'t have a description')
                continue
            try:
                lostfilm_num = LOSTFILM_ID_REGEXP.search(item['description']).groups()
            except Exception:
                log.debug('Item doesn\'t have lostfilm id in description')
                continue
            try:
                season_num, episode_num = [
                    int(x) for x in EPISODE_REGEXP.search(item['link']).groups()
                ]
            except Exception:
                log.debug('Item doesn\'t have episode id in link')
                continue
            params = {'c': lostfilm_num, 's': season_num, 'e': episode_num}
            redirect_url = 'http://www.lostfilm.tv/v_search.php'
            try:
                response = task.requests.get(redirect_url, params=params)
            except RequestException as e:
                log.error('Could not connect to redirect url: {:s}'.format(e))
                continue

            page = get_soup(response.content)
            try:
                redirect_url = page.head.meta['content'].split('url=')[1]
            except Exception:
                log.error('Missing redirect')
                continue

            try:
                response = task.requests.get(redirect_url)
            except RequestException as e:
                log.error('Could not connect to redirect url2: {:s}'.format(e))
                continue

            page = get_soup(response.content)

            episode_name_rus = episode_name_eng = series_name_rus = None
            series_name_eng = None
            try:
                series_name_rus = page.find('div', 'inner-box--title').text.strip()
                title_eng_div = page.find('div', 'inner-box--subtitle').text.strip() or None
                series_name_eng = (
                    (title_eng_div.endswith(', сериал')) and title_eng_div[:-8] or None
                )
                text_div = page.find('div', 'inner-box--text').text.strip() or None
                episode_name_rus, episode_name_eng = TEXT_REGEXP.findall(text_div).pop()
                episode_name_rus = episode_name_rus.strip()
                episode_name_eng = episode_name_eng.strip()
            except Exception:
                log.debug('Cannot parse head info')
                continue

            episode_id = 'S{:02d}E{:02d}'.format(season_num, episode_num)

            for item in page.findAll('div', 'inner-box--item'):
                torrent_link = quality = None
                try:
                    torrent_link = item.find('div', 'inner-box--link sub').a['href']
                    quality = item.find('div', 'inner-box--label').text.strip()
                except Exception:
                    log.debug('Item doesn\'t have a link or quality')
                    continue
                if torrent_link is None or quality is None:
                    log.debug('Item doesn\'t have a link or quality')
                    continue
                if quality_map.get(quality):
                    quality, file_ext = quality_map.get(quality)
                else:
                    file_ext = 'avi'
                if series_name_eng:
                    new_title = '.'.join(
                        [
                            series_name_eng,
                            episode_id,
                            quality,
                            'rus.LostFilm.TV',
                            file_ext,
                            'torrent',
                        ]
                    ).replace(' ', '.')
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
