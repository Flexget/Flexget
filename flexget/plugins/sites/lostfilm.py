# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

__author__ = 'danfocus'

log = logging.getLogger('lostfilm')

EPISODE_REGEXP = re.compile(
    '.*lostfilm.tv/series/.*/season_(\d+)/episode_(\d+)/.*')
LOSTFILM_ID_REGEXP = re.compile(
    '.*static.lostfilm.tv/Images/(\d+)/Posters/poster.jpg.*')
TEXT_REGEXP = re.compile('^(\d+)\sсезон\s(\d+)\sсерия\.\s(.+)\s\((.+)\)$')

quality_map = {
    'SD': ('480p', 'avi'),
    '1080': ('1080p', 'mkv'),
    'MP4': ('720p', 'mp4'),
    'HD': ('720p', 'mkv')
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
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
        },
        'additionalProperties': False
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
        rss = feedparser.parse(config['url'])
        if rss.get('status') != 200:
            log.error('Received not 200 (OK) status')
            return
        entries = []
        for item in rss.entries:
            if item.get('link') is None:
                log.debug('Item doesn\'t have a link')
                continue
            if item.get('description') is None:
                log.debug('Item doesn\'t have a description')
                continue
            match = LOSTFILM_ID_REGEXP.search(item['description'])
            if match:
                lostfilm_num = match.group(1)
            else:
                log.debug('Item doesn\'t have lostfilm id in description')
                continue
            match = EPISODE_REGEXP.match(item['link'])
            if match:
                season_num = int(match.group(1))
                episode_num = int(match.group(2))
            else:
                log.debug('Item doesn\'t have episode id in link')
                continue
            redirect_url = 'http://www.lostfilm.tv/v_search.php?' \
                'c={}&s={}&e={}'.format(lostfilm_num, season_num, episode_num)
            try:
                response = task.requests.get(redirect_url)
            except RequestException as e:
                log.error('Could not connect to redirect url: {:s}'.format(e))
                continue

            page = get_soup(response.content)
            try:
                redirect_url = page.head.meta['content'].split('url=')[1]
            except:
                log.error('Missing redirect')
                continue

            try:
                response = task.requests.get(redirect_url)
            except RequestException as e:
                log.error('Could not connect to redirect url2: {:s}'.format(e))
                continue

            page = get_soup(response.content)

            new_title_template = episode_name_rus = episode_name_eng \
                = series_name_rus = series_name_eng = None
            try:
                series_name_rus = page.find(
                    'div', 'inner-box--title').text.strip() or None
                title_eng_div = page.find(
                    'div', 'inner-box--subtitle').text.strip() or None
                series_name_eng = title_eng_div[:-8] \
                    if title_eng_div.endswith(', сериал') else None
                text_div = page.find('div', 'inner-box--text').text.strip() \
                    or None
                match = TEXT_REGEXP.match(text_div)
                if match:
                    season_num = int(match.group(1).strip())
                    episode_num = int(match.group(2).strip())
                    episode_name_rus = match.group(3).strip()
                    episode_name_eng = match.group(4).strip()
                if series_name_eng and season_num and episode_num:
                    new_title_template = \
                        '{}.S{:02d}E{:02d}.{{}}.rus.LostFilm.TV.{{}}.torrent'\
                        .format(series_name_eng, season_num, episode_num)
            except:
                pass

            for item in page.findAll('div', 'inner-box--item'):
                torrent_link = item.find(
                    'div', 'inner-box--link sub').a['href'] or None
                quality = item.find('div', 'inner-box--label').text.strip() \
                    or None
                if torrent_link is None or quality is None:
                    continue
                if new_title_template:
                    new_title = new_title_template.format(
                        quality_map.get(quality, (quality, None))[0],
                        quality_map.get(quality, (None, 'avi'))[1]
                        ).replace(' ', '.')
                else:
                    if item.get('title') is not None:
                        new_title = '%s %s'.format(
                            item['title'],
                            quality_map.get(quality, (quality, None))[0])
                    else:
                        log.error('Item doesn\'t have a title')
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
