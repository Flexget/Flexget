import logging
from flexget.plugin import register_plugin, internet
from flexget.manager import Base, Session
from flexget.utils.tools import urlopener
from BeautifulSoup import BeautifulStoneSoup
from sqlalchemy import Column, Integer, Unicode, DateTime, String
from datetime import datetime, timedelta
import urllib2
from flexget.plugins.filter_series import FilterSeriesBase

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


class FilterThetvdbFavorites(FilterSeriesBase):
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
        self.build_options_validator(root)
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
                    log.debug('Looking up series info for %s' % str(fid))
                    data = BeautifulStoneSoup(urlopener("http://thetvdb.com/data/series/%s/" % str(fid), log), \
                        convertEntities=BeautifulStoneSoup.HTML_ENTITIES)
                    items.append(ThetvdbFavorites(account_id, data.series.seriesname.string))
            except (urllib2.URLError, IOError, AttributeError):
                import traceback
                # If there are errors getting the favorites or parsing the xml, fall back on cache
                log.error('Error retrieving favorites from thetvdb, using cache.')
                log.debug(traceback.format_exc())
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
        series_group = config.get('series_group', 'thetvdb_favs')
        # Pass all config options to series plugin except our special ones
        group_config = dict([(key, config[key]) for key in config if not key in ['account_id', 'series_group', 'strip_dates']])
        tvdb_series_config = {series_group: []}
        for series in cache:
            if ("strip_dates" in config) and (config['strip_dates']) and (series.series_name[-1] == ')'):
                series_regex = "^" + series.series_name.rstrip('()1234567890').replace("(", "").replace(")", "").replace(" ", ".?").lower()
                series_name = series.series_name.replace("(", "").replace(")", "")
                if group_config == {}:
                    series_entry = {series_name: {"name_regexp": series_regex}}
                else:
                    series_entry = {series_name: group_config}
                    if "name_regexp" in series_entry[series_name]:
                        series_entry["name_regexp"].append(series_regex)
                    else:
                        series_entry["name_regexp"] = [series_regex]
            else:
                if group_config == {}:
                    series_entry = series.series_name.replace("(", "").replace(")", "")
                else:
                    series_entry = {series.series_name.replace("(", "").replace(")", ""): group_config}
            tvdb_series_config[series_group].append(series_entry)
        # Merge the our config in to the main series config
        self.merge_config(feed, tvdb_series_config)

# needs to occur prior to the series plugin, in order to deal with the group settings stuff.
register_plugin(FilterThetvdbFavorites, 'thetvdb_favorites')
