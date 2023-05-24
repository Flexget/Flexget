import re
from itertools import chain

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.soup import get_soup

logger = logger.bind(name='myepisodes_list')

URL = 'http://www.myepisodes.com/'


class MyEpisodesList:
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
    @plugin.internet(logger)
    def on_task_input(self, task, config):
        if not task.requests.cookies:
            username = config['username']
            password = config['password']

            logger.debug('Logging in to {} ...', URL)
            params = {'username': username, 'password': password, 'action': 'Login'}
            try:
                loginsrc = task.requests.post(URL + 'login.php', data=params)
                if 'login' in loginsrc.url:
                    raise plugin.PluginWarning(
                        (
                            'Login to myepisodes.com failed, please check '
                            'your account data or see if the site is down.'
                        ),
                        logger,
                    )
            except RequestException as e:
                raise plugin.PluginError("Error logging in to myepisodes: %s" % e)

        page = task.requests.get(URL + "myshows/manage/").content
        try:
            soup = get_soup(page)
        except Exception as e:
            raise plugin.PluginError(f"Unable to parse myepisodes.com page: {e}")

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
            url = f'{URL}views.php?type=epsbyshow&showid={showid}'

            entry = Entry()
            entry['title'] = name
            entry['url'] = url
            entry['series_name'] = name
            entry['myepisodes_id'] = showid

            if entry.isvalid():
                entries.append(entry)
            else:
                logger.debug('Invalid entry created? {}', entry)

        if not entries:
            logger.warning(
                "No shows found on myepisodes.com list. Maybe you need to add some first?"
            )

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(MyEpisodesList, 'myepisodes_list', api_ver=2, interfaces=['task'])
