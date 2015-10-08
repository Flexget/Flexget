from __future__ import unicode_literals, division, absolute_import
import logging
import re
from itertools import chain

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.soup import get_soup

log = logging.getLogger('myepisodes')

URL = 'http://www.myepisodes.com/'


class MyEpisodesList(object):
    """Creates an entry for each item in your myepisodes.com show list.

    Syntax:

    myepisodes_list:
      username: <value>
      password: <value>
      strip_dates: <yes|no>
      include_ignored: <yes|no>

    Options username and password are required.
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'strip_dates': {'type': 'boolean', 'default': False},
            'include_ignored': {'type': 'boolean', 'default': False},
        },
        'required': ['username', 'password'],
        'additionalProperties': False,
    }

    @cached('myepisodes_list')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        if not task.requests.cookies:
            username = config['username']
            password = config['password']

            log.debug("Logging in to %s ..." % URL)
            params = {
                'username': username,
                'password': password,
                'action': 'Login'
            }
            loginsrc = task.requests.post(URL + 'login.php', data=params).content
            if str(username) not in loginsrc:
                raise plugin.PluginWarning(('Login to myepisodes.com failed, please check '
                                 'your account data or see if the site is down.'), log)

        page = task.requests.get(URL + "shows.php?type=manage").content
        try:
            soup = get_soup(page)
        except Exception as e:
            raise plugin.PluginError("Unable to parse myepisodes.com page: %s" % (e,))

        entries = []

        def show_list(select_id):
            return soup.find('select', {'id': select_id}).findAll('option')

        options = show_list('shows')
        if config['include_ignored']:
            options = chain(options, show_list('ignored_shows'))
        for option in options:
            name = option.text
            if config.get('strip_dates'):
                # Remove year from end of name if present
                name = re.sub(r'\s+\(\d{4}\)$', '', name)
            showid = option.get('value')
            url = '%sviews.php?type=epsbyshow&showid=%s' % (URL, showid)

            entry = Entry()
            entry['title'] = name
            entry['url'] = url
            entry['series_name'] = name
            entry['myepisodes_id'] = showid

            if entry.isvalid():
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)

        if not entries:
            log.warn("No shows found on myepisodes.com list. Maybe you need to add some first?")

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(MyEpisodesList, 'myepisodes_list', api_ver=2)
