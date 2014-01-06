from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import urllib2
import re
import cookielib
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from flexget import db_schema, plugin
from flexget.event import event

try:
    from flexget.plugins.api_tvdb import lookup_series
except ImportError:
    raise plugin.DependencyError(issued_by='myepisodes', missing='api_tvdb',
                                 message='myepisodes requires the `api_tvdb` plugin')


log = logging.getLogger('myepisodes')
Base = db_schema.versioned_base('myepisodes', 0)


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
        return '<MyEpisodesInfo(series_name=%s, myepisodes_id=%s)>' % (self.series_name, self.myepisodes_id)


class MyEpisodes(object):
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
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'}
        },
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        """Mark all accepted episodes as acquired on MyEpisodes"""
        if not task.accepted:
            # Nothing accepted, don't do anything
            return

        username = config['username']
        password = config['password']

        cookiejar = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
        baseurl = urllib2.Request('http://www.myepisodes.com/login.php?')
        loginparams = urllib.urlencode({'username': username,
                                        'password': password,
                                        'action': 'Login'})
        try:
            logincon = opener.open(baseurl, loginparams)
            loginsrc = logincon.read()
        except urllib2.URLError as e:
            log.error('Error logging in to myepisodes: %s' % e)
            return

        if str(username) not in loginsrc:
            raise plugin.PluginWarning(('Login to myepisodes.com failed, please check '
                                 'your account data or see if the site is down.'), log)

        for entry in task.accepted:
            try:
                self.mark_episode(task, entry, opener)
            except plugin.PluginWarning as w:
                log.warning(str(w))

    def lookup_myepisodes_id(self, entry, opener, session):
        """Populates myepisodes_id field for an entry, and returns the id.

        Call will also set entry field `myepisode_id` if successful.

        Return:
            myepisode id

        Raises:
            LookupError if entry does not have field series_name
        """

        # Don't need to look it up if we already have it.
        if entry.get('myepisodes_id'):
            return entry['myepisodes_id']

        if not entry.get('series_name'):
            raise LookupError('Cannot lookup myepisodes id for entries without series_name')
        series_name = entry['series_name']

        # First check if we already have a myepisodes id stored for this series
        myepisodes_info = session.query(MyEpisodesInfo).\
            filter(MyEpisodesInfo.series_name == series_name.lower()).first()
        if myepisodes_info:
            entry['myepisodes_id'] = myepisodes_info.myepisodes_id
            return myepisodes_info.myepisodes_id

        # Get the series name from thetvdb to increase match chance on myepisodes
        if entry.get('tvdb_series_name'):
            query_name = entry['tvdb_series_name']
        else:
            try:
                series = lookup_series(name=series_name, tvdb_id=entry.get('tvdb_id'))
                query_name = series.seriesname
            except LookupError as e:
                log.warning('Unable to lookup series `%s` from tvdb, using raw name.' % series_name)
                query_name = series_name

        baseurl = urllib2.Request('http://www.myepisodes.com/search.php?')
        params = urllib.urlencode({'tvshow': query_name, 'action': 'Search myepisodes.com'})
        try:
            con = opener.open(baseurl, params)
            txt = con.read()
        except urllib2.URLError as e:
            log.error('Error searching for myepisodes id: %s' % e)

        matchObj = re.search(r'&showid=([0-9]*)">' + query_name + '</a>', txt, re.MULTILINE | re.IGNORECASE)
        if matchObj:
            myepisodes_id = matchObj.group(1)
            db_item = session.query(MyEpisodesInfo).filter(MyEpisodesInfo.myepisodes_id == myepisodes_id).first()
            if db_item:
                log.info('Changing name to `%s` for series with myepisodes_id %s' %
                    (series_name.lower(), myepisodes_id))
                db_item.series_name = series_name.lower()
            else:
                session.add(MyEpisodesInfo(series_name.lower(), myepisodes_id))
            entry['myepisodes_id'] = myepisodes_id
            return myepisodes_id

    def mark_episode(self, task, entry, opener):
        """Mark episode as acquired.

        Required entry fields:
            - series_name
            - series_season
            - series_episode

        Raises:
            PluginWarning if operation fails
        """

        if 'series_season' not in entry or 'series_episode' not in entry or 'series_name' not in entry:
            raise plugin.PluginWarning(
                'Can\'t mark entry `%s` in myepisodes without series_season, series_episode and series_name fields' %
                entry['title'], log)

        if not self.lookup_myepisodes_id(entry, opener, session=task.session):
            raise plugin.PluginWarning('Couldn\'t get myepisodes id for `%s`' % entry['title'], log)

        myepisodes_id = entry['myepisodes_id']
        season = entry['series_season']
        episode = entry['series_episode']

        if task.options.test:
            log.info('Would mark %s of `%s` as acquired.' % (entry['series_id'], entry['series_name']))
        else:
            baseurl2 = urllib2.Request(
                'http://www.myepisodes.com/myshows.php?action=Update&showid=%s&season=%s&episode=%s&seen=0' %
                (myepisodes_id, season, episode))
            opener.open(baseurl2)
            log.info('Marked %s of `%s` as acquired.' % (entry['series_id'], entry['series_name']))


@event('plugin.register')
def register_plugin():
    plugin.register(MyEpisodes, 'myepisodes', api_ver=2)
