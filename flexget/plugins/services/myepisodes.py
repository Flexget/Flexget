import re
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String

from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.event import event
from flexget.utils import requests

logger = logger.bind(name='myepisodes')
Base = versioned_base('myepisodes', 0)


class MyEpisodesInfo(Base):
    __tablename__ = 'myepisodes'

    id = Column(Integer, primary_key=True)
    series_name = Column(String, unique=True)
    myepisodes_id = Column(Integer, unique=True)
    updated = Column(DateTime)

    def __init__(self, series_name, myepisodes_id):
        self.series_name = series_name
        self.myepisodes_id = myepisodes_id
        self.updated = datetime.now()

    def __repr__(self):
        return '<MyEpisodesInfo(series_name={}, myepisodes_id={})>'.format(
            self.series_name,
            self.myepisodes_id,
        )


class MyEpisodes:
    """
    Marks a series episode as acquired in your myepisodes.com account.

    Simple Example:

    Most shows are recognized automatically from their TVDBname.
    And of course the plugin needs to know your MyEpisodes.com account details.

    tasks:
      tvshows:
        myepisodes:
          username: <username>
          password: <password>
        series:
         - human target
         - chuck

    Advanced Example:

    In some cases, the TVDB name is either not unique or won't even be discovered.
    In that case you need to specify the MyEpisodes id manually using the set plugin.

    tasks:
      tvshows:
        myepisodes:
          username: <username>
          password: <password>
        series:
         - human target:
             set:
               myepisodes_id: 5111
         - chuck

    How to find the MyEpisodes id: http://matrixagents.org/screencasts/myep_example-20110507-131555.png
    """

    schema = {
        'type': 'object',
        'properties': {'username': {'type': 'string'}, 'password': {'type': 'string'}},
        'required': ['username', 'password'],
        'additionalProperties': False,
    }

    def __init__(self):
        self.plugin_config = None
        self.db_session = None
        self.test_mode = None
        self.http_session = None

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_output(self, task, config):
        """
        Mark all accepted episodes as acquired on MyEpisodes
        """

        if not task.accepted:
            # Nothing accepted, don't do anything
            return

        try:
            self.plugin_config = config
            self.db_session = task.session
            self.test_mode = task.options.test

            # attempt authentication
            self.http_session = self._login(config)

        except plugin.PluginWarning as w:
            logger.warning(w)
            return

        except plugin.PluginError as e:
            logger.error(e)
            return

        for entry in task.accepted:
            # mark the accepted entries as acquired
            try:
                self._validate_entry(entry)
                entry['myepisodes_id'] = self._lookup_myepisodes_id(entry)
                self._mark_episode_acquired(entry)

            except plugin.PluginWarning as w:
                logger.warning(w)

    def _validate_entry(self, entry):
        """
        Checks an entry for all of the fields needed to comunicate with myepidoes
        Return: boolean
        """
        if (
            'series_season' not in entry
            or 'series_episode' not in entry
            or 'series_name' not in entry
        ):
            raise plugin.PluginWarning(
                'Can\'t mark entry `%s` in myepisodes without series_season, series_episode and series_name '
                'fields' % entry['title'],
                logger,
            )

    def _lookup_myepisodes_id(self, entry):
        """
        Attempts to find the myepisodes id for the series
        Return: myepisode id or None
        """

        # Do we already have the id?
        myepisodes_id = entry.get('myepisodes_id')
        if myepisodes_id:
            return myepisodes_id

        # have we previously recorded the id for this series?
        myepisodes_id = self._retrieve_id_from_database(entry)
        if myepisodes_id:
            return myepisodes_id

        # We don't know the id for this series, so it's time to search myepisodes.com for it
        myepisodes_id = self._retrieve_id_from_website(entry)
        if myepisodes_id:
            return myepisodes_id

        raise plugin.PluginWarning(
            'Unable to determine the myepisodes id for: `%s`' % entry['title'], logger
        )

    def _retrieve_id_from_database(self, entry):
        """
        Attempts to find the myepisodes id in the database
        Return: myepisode id or None
        """
        lc_series_name = entry['series_name'].lower()
        info = (
            self.db_session.query(MyEpisodesInfo)
            .filter(MyEpisodesInfo.series_name == lc_series_name)
            .first()
        )
        if info:
            return info.myepisodes_id

    def _retrieve_id_from_website(self, entry):
        """
        Attempts to find the myepisodes id for the series for the website itself
        Return: myepisode id or None
        """
        myepisodes_id = None
        baseurl = 'http://www.myepisodes.com/search/'
        search_value = self._generate_search_value(entry)

        payload = {'tvshow': search_value, 'action': 'Search'}

        try:
            response = self.http_session.post(baseurl, data=payload)
            regex = r'"/epsbyshow\/([0-9]*)\/.*">' + search_value + '</a>'
            match_obj = re.search(regex, response.text, re.MULTILINE | re.IGNORECASE)
            if match_obj:
                myepisodes_id = match_obj.group(1)
                self._save_id(search_value, myepisodes_id)

        except requests.RequestException as e:
            raise plugin.PluginError('Error searching for myepisodes id: %s' % e)

        return myepisodes_id

    def _generate_search_value(self, entry):
        """
        Find the TVDB name for searching myepisodes with.

        myepisodes.com is backed by tvrage, so this will not be perfect.

        Return: myepisode id or None
        """
        search_value = entry['series_name']

        # Get the series name from thetvdb to increase match chance on myepisodes
        if entry.get('tvdb_series_name'):
            search_value = entry['tvdb_series_name']
        else:
            try:
                series = plugin.get('api_tvdb', self).lookup_series(
                    name=entry['series_name'], tvdb_id=entry.get('tvdb_id')
                )
                search_value = series.name
            except LookupError:
                logger.warning(
                    'Unable to lookup series `{}` from tvdb, using raw name.', entry['series_name']
                )

        return search_value

    def _save_id(self, series_name, myepisodes_id):
        """
        Save the myepisodes id in the database.
        This will help prevent unecceary communication with the website
        """

        # if we already have the a record for that id, update the name so that we find it next time
        db_item = (
            self.db_session.query(MyEpisodesInfo)
            .filter(MyEpisodesInfo.myepisodes_id == myepisodes_id)
            .first()
        )
        if db_item:
            logger.info(
                'Changing name to `{}` for series with myepisodes_id {}',
                series_name.lower(),
                myepisodes_id,
            )
            db_item.series_name = series_name.lower()
        else:
            self.db_session.add(MyEpisodesInfo(series_name.lower(), myepisodes_id))

    def _mark_episode_acquired(self, entry):
        """Mark episode as acquired.

        Required entry fields:
            - series_name
            - series_season
            - series_episode

        Raises:
            PluginWarning if operation fails
        """

        url = "http://www.myepisodes.com/ajax/service.php?mode=eps_update"
        myepisodes_id = entry['myepisodes_id']
        season = entry['series_season']
        episode = entry['series_episode']

        super_secret_code = f"A{str(myepisodes_id)}-{str(season)}-{str(episode)}"

        payload = {super_secret_code: "true"}

        if self.test_mode:
            logger.info(
                'Would mark {} of `{}` as acquired.', entry['series_id'], entry['series_name']
            )
            return

        try:
            self.http_session.post(url, data=payload)

        except requests.RequestException:
            raise plugin.PluginError(
                'Failed to mark {} of `{}` as acquired.'.format(
                    entry['series_id'], entry['series_name']
                )
            )

        logger.info('Marked {} of `{}` as acquired.', entry['series_id'], entry['series_name'])

    def _login(self, config):
        """Authenicate with the myepisodes service and return a requests session

        Return:
            requests session

        Raises:
            PluginWarning if login fails
            PluginError if http communication fails
        """

        url = "https://www.myepisodes.com/login.php"
        session = requests.Session()

        payload = {
            'username': config['username'],
            'password': config['password'],
            'action': 'Login',
        }

        try:
            response = session.post(url, data=payload)

            if 'login' in response.url:
                raise plugin.PluginWarning(
                    (
                        'Login to myepisodes.com failed, please see if the site is down and verify '
                        'your credentials.'
                    ),
                    logger,
                )
        except requests.RequestException as e:
            raise plugin.PluginError('Error logging in to myepisodes: %s' % e)

        return session


@event('plugin.register')
def register_plugin():
    plugin.register(MyEpisodes, 'myepisodes', api_ver=2)
