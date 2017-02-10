# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

__author__ = 'danfocus'

log = logging.getLogger('lostfilm')


class LostFilm(object):
    """
    Change new lostfilm's rss links

    Example::

      lostfilm: yes
    """

    schema = {'type': 'boolean'}

    episode_reg = re.compile(
        '.*lostfilm.tv/series/.*/season_(\d+)/episode_(\d+)/.*')
    lostfilm_reg = re.compile(
        '.*static.lostfilm.tv/Images/(\d+)/Posters/poster.jpg.*')
    text_reg = re.compile('^(\d+)\sсезон\s(\d+)\sсерия\.\s(.+)\s\((.+)\)$')

    quality_map = {
        'SD': ('480p', 'avi'),
        '1080': ('1080p', 'mkv'),
        'MP4': ('720p', 'mp4'),
        'HD': ('720p', 'mkv')
    }

    @plugin.priority(-1)
    def on_task_input(self, task, config):
        if config is False:
            return
        entries = []
        for entry in task.entries:
            if entry.get('url') is None:
                entry.reject('Entry doesn\'t have a url')
                continue
            if entry.get('description') is None:
                entry.reject('Entry doesn\'t have a description')
                continue
            match = self.lostfilm_reg.search(entry['description'])
            if match:
                lostfilm_num = match.group(1)
            else:
                entry.reject('Entry doesn\'t have lostfilm id in description')
                continue
            match = self.episode_reg.match(entry['url'])
            if match:
                season_num = match.group(1)
                episode_num = match.group(2)
            else:
                entry.reject('Entry doesn\'t have episode id in link')
                continue
            redirect_url = 'https://www.lostfilm.tv/v_search.php?' \
                'c=%s&s=%s&e=%s' % (lostfilm_num, season_num, episode_num)
            try:
                response = task.requests.get(redirect_url,
                                             headers=task.requests.headers)
            except RequestException as e:
                entry.reject('Could not connect to redirect url: %s' % e)
                continue

            page = get_soup(response.content)
            try:
                redirect_url = page.head.meta['content'].split("url=")[1]
            except:
                entry.reject('Missing redirect')
                continue

            try:
                response = task.requests.get(redirect_url,
                                             headers=task.requests.headers)
            except RequestException as e:
                entry.reject('Could not connect to redirect url 2: %s' % e)
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
                    if title_eng_div.endswith(", сериал") else None
                text_div = page.find('div', 'inner-box--text').text.strip() \
                    or None
                match = self.text_reg.match(text_div)
                if match:
                    season_num = int(match.group(1).strip())
                    episode_num = int(match.group(2).strip())
                    episode_name_rus = match.group(3).strip()
                    episode_name_eng = match.group(4).strip()
                if series_name_eng and season_num and episode_num:
                    new_title_template = \
                        "{}.S{:02d}E{:02d}.{{}}.rus.LostFilm.TV.{{}}.torrent"\
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
                        self.quality_map.get(quality)[0] or quality,
                        self.quality_map.get(quality)[1] or 'avi'
                        ).replace(' ', '.')
                else:
                    new_title = entry['title'] + " " \
                        + self.quality_map.get(quality)[0] or quality
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
            entry.reject("Original entry rejected")

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(LostFilm, 'lostfilm', api_ver=2)
