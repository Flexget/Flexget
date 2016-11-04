from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup

log = logging.getLogger('pogcal')


class InputPogDesign(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'}
        },
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    name_map = {'The Tonight Show [Leno]': 'The Tonight Show With Jay Leno',
                'Late Show [Letterman]': 'David Letterman'}

    def on_task_input(self, task, config):
        session = requests.Session()
        data = {'username': config['username'], 'password': config['password'], 'sub_login': 'Account Login'}
        try:
            r = session.post('http://www.pogdesign.co.uk/cat/login', data=data)
            if 'U / P Invalid' in r.text:
                raise plugin.PluginError('Invalid username/password for pogdesign.')
            page = session.get('http://www.pogdesign.co.uk/cat/show-select')
        except requests.RequestException as e:
            raise plugin.PluginError('Error retrieving source: %s' % e)
        soup = get_soup(page.text)
        entries = []
        for row in soup.find_all('li', {'class': 'selectgrp checked'}):

            # Get name
            t = row.find('strong')

            # Remove <span> tags
            spantags = t.find_all('span')
            for s in spantags:
                s.extract()
            t = row.text
            # remove newlines and whitepsace
            t = t.replace('\n', '').strip()

            if t.endswith('[The]'):
                t = 'The ' + t[:-6]

            # Make certain names friendlier
            if t in self.name_map:
                t = self.name_map[t]

            e = Entry()
            e['title'] = t
            e['url'] = 'http://www.pogdesign.co.uk/{0}'.format(row.find_next('a')['href'].lstrip('/'))
            entries.append(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputPogDesign, 'pogcal', api_ver=2)
