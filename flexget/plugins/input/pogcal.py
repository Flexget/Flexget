from __future__ import unicode_literals, division, absolute_import
import logging

from bs4 import BeautifulSoup

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests

log = logging.getLogger('pogcal')


class InputPogDesign(object):

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='username', required=True)
        config.accept('text', key='password', required=True)
        return config

    name_map = {'The Tonight Show [Leno]': 'The Tonight Show With Jay Leno',
                'Late Show [Letterman]': 'David Letterman'}

    def on_task_input(self, task, config):
        session = requests.Session()
        data = {'username': config['username'], 'password': config['password'], 'sub_login': 'Account Login'}
        try:
            r = session.post('http://www.pogdesign.co.uk/cat/', data=data)
            if 'U / P Invalid' in r.text:
                raise plugin.PluginError('Invalid username/password for pogdesign.')
            page = session.get('http://www.pogdesign.co.uk/cat/showselect.php')
        except requests.RequestException as e:
            raise plugin.PluginError('Error retrieving source: %s' % e)
        soup = BeautifulSoup(page.text)
        entries = []
        for row in soup.find_all('label', {'class': 'label_check'}):
            if row.find(attrs={'checked': 'checked'}):
                t = row.find('strong').text
                if t.endswith('[The]'):
                    t = 'The ' + t[:-6]

                # Make certain names friendlier
                if t in self.name_map:
                    t = self.name_map[t]

                e = Entry()
                e['title'] = t
                url = row.find_next('a', {'class': 'slink'})
                e['url'] = 'http://www.pogdesign.co.uk' + url['href']
                entries.append(e)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputPogDesign, 'pogcal', api_ver=2)
