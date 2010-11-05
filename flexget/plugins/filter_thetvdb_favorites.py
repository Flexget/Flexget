import logging
from flexget.plugin import register_plugin, internet, get_plugin_by_name, PluginError
from flexget.manager import Base, Session
from flexget.utils.tools import urlopener
from BeautifulSoup import BeautifulStoneSoup
from sqlalchemy import Column, Integer, Unicode, DateTime, String
from datetime import datetime, timedelta
import urllib2

log = logging.getLogger('thetvdb_favorites')


class ThetvdbFavorites(Base):

    __tablename__ = 'thetvdb_favorites'

    id = Column(Integer, primary_key=True)
    account_id = Column(String, index=True)
    series_name = Column(Unicode)
    added = Column(DateTime)

    def __init__(self, account_id, series_name):
        self.series_name = series_name
        self.account_id = account_id
        self.added = datetime.now()

    def __repr__(self):
        return '<series_favorites(account_id=%s, series_name=%s)>' % (self.account_id, self.series_name)


class FilterThetvdbFavorites:
    """
        Creates a series config containing all your thetvdb.com favorites

        Example:

        thetvdb_favorites:
          account_id: 23098230
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('text', key='account_id', required=True)
        root.accept('text', key='series_group')
        return root

    @internet(log)
    def on_process_start(self, feed):
        config = feed.config.get('thetvdb_favorites')
        account_id = str(config['account_id'])
        session = Session()
        cache = session.query(ThetvdbFavorites).filter(ThetvdbFavorites.account_id == account_id)
        if cache.count() and cache.first().added > datetime.now() - timedelta(minutes=1):
            log.debug('Using cached thetvdb favorites')
        else:
            log.debug('Updating favorites from thetvdb.com')
            try:
                url = 'http://thetvdb.com/api/User_Favorites.php?accountid=%s' % account_id
                log.debug('requesting %s' % url)
                data = BeautifulStoneSoup(urlopener(url, log))
                favorite_ids = []
                for i in data.favorites.findAll("series", recursive=False):
                    favorite_ids.append(int(i.string))
                # We found new data, remove old cached data
                items = []
                for fid in favorite_ids:
                    data = BeautifulStoneSoup(urlopener("http://thetvdb.com/data/series/%s/" % str(fid), log), \
                        convertEntities=BeautifulStoneSoup.HTML_ENTITIES)
                    items.append(ThetvdbFavorites(account_id, data.series.seriesname.string))
            except (urllib2.URLError, IOError, AttributeError):
                # If there are errors getting the favorites or parsing the xml, fall back on cache
                log.error('Error retrieving favorites from thetvdb, using cache.')
            else:
                # Successfully updated from tvdb, update the database
                log.debug('Successfully updated favorites from thetvdb.com')
                cache.delete()
                session.add_all(items)
                session.commit()
                cache = session.query(ThetvdbFavorites).filter(ThetvdbFavorites.account_id == account_id)
        if not cache.count():
            log.info("Didn't find any thetvdb.com favorites.")
            return
        tvdb_series_config = {}
        series_group = config.get('series_group', 'thetvdb_favs')
        tvdb_series_config[series_group] = []
        for series in cache:
            tvdb_series_config[series_group].append(series.series_name)
        # If the series plugin is not configured on this feed, make a blank config
        if not 'series' in feed.config:
            feed.config['series'] = {}
        elif not isinstance(feed.config['series'], dict):
            # Call series plugin generate_config to expand series config to group format
            feed.config['series'] = get_plugin_by_name('series').instance.generate_config(feed)
        # Merge the tvdb shows in to the main series config
        from flexget.utils.tools import MergeException, merge_dict_from_to
        try:
            merge_dict_from_to(tvdb_series_config, feed.config['series'])
        except MergeException:
            raise PluginError('Failed to merge thetvdb favorites to feed %s, incompatible datatypes' % feed.name)


register_plugin(FilterThetvdbFavorites, 'thetvdb_favorites')
