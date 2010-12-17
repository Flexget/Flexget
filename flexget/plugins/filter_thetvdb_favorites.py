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
    series_id = Column(Unicode)
    added = Column(DateTime)

    def __init__(self, account_id, series_name, series_id):
        self.series_name = series_name
        self.account_id = account_id
        self.series_id = series_id
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
        root.accept('boolean', key='strip_dates')
        self.build_options_validator(root)
        return root

    @internet(log)
    def on_feed_start(self, feed):
        config = feed.config.get('thetvdb_favorites')
        account_id = str(config['account_id'])
        session = Session()
        # Check when the last time the user information (favorites) were updated.
        # The user info is stored where a series_id == ""
        user_update = session.query(ThetvdbFavorites).filter(ThetvdbFavorites.account_id == account_id).filter(ThetvdbFavorites.series_id == unicode(""))
        # Grab all info from cache just in case.
        cache = session.query(ThetvdbFavorites).filter(ThetvdbFavorites.account_id == account_id).filter(ThetvdbFavorites.series_id != unicode(""))
        if cache.count() and user_update.count() and user_update.first().added > datetime.now() - timedelta(minutes=1):
            log.debug('Using cached thetvdb favorite series information for account ID %s' % account_id)
        else:
            # Wipe out previous user info update time
            user_update.delete()
            session.add(ThetvdbFavorites(account_id, unicode("User Series List Update Time"), unicode("")))
            session.commit()
            log.debug('Updating favorite series information from thetvdb.com for account ID %s' % account_id)
            try:
                url = 'http://thetvdb.com/api/User_Favorites.php?accountid=%s' % account_id
                log.debug('requesting %s' % url)
                data = BeautifulStoneSoup(urlopener(url, log))
                favorite_ids = []
                for i in data.favorites.findAll("series", recursive=False):
                    favorite_ids.append(i.string)
                # We found new data, check each show, and if older than
                # 3 hours, update the individual series information
                items = []
                for fid in favorite_ids:
                    fidcache = cache.filter(ThetvdbFavorites.series_id == fid)
                    if fidcache.count() and fidcache.first().added > datetime.now() - timedelta(hours=3):
                        series_name = fidcache.first().series_name
                        log.debug('Using series info from cache for %s - %s' % (str(fid), str(series_name)))
                        items.append(ThetvdbFavorites(account_id, series_name, fid))
                    else:
                        log.debug('Looking up series info for %s' % str(fid))
                        data = BeautifulStoneSoup(urlopener("http://thetvdb.com//data/series/%s/" % str(fid), log), \
                            convertEntities=BeautifulStoneSoup.HTML_ENTITIES)
                        items.append(ThetvdbFavorites(account_id, data.series.seriesname.string, data.series.id.string))
                        if len(items) % 10 == 0:
                            log.info("Parsed %i of %i series from thetvdb favorites" % (len(items), len(favorite_ids)))
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
                cache = session.query(ThetvdbFavorites).filter(ThetvdbFavorites.account_id == account_id).filter(ThetvdbFavorites.series_id != unicode(""))
        if not cache.count():
            log.info("Didn't find any thetvdb.com favorites.")
            return
        series_group = config.get('series_group', 'thetvdb_favs')
        # Pass all config options to series plugin except our special ones
        tvdb_series_config = {series_group: []}
        for series in cache:
            group_config = dict([(key, config[key]) for key in config if not key in ['account_id', 'series_group', 'strip_dates']])
            if ("strip_dates" in config) and (config['strip_dates']) and (series.series_name[-1] == ')'):
                series_regex = "^" + series.series_name.rstrip('()1234567890').replace("(", "").replace(")", "").replace(" ", ".?").lower()
                series_name = series.series_name.replace("(", "").replace(")", "")
                if group_config == {}:
                    series_entry = {series_name: {"name_regexp": series_regex}}
                else:
                    series_entry = {series_name: group_config}
                    if "name_regexp" in series_entry[series_name]:
                        series_entry[series_name]["name_regexp"].append(series_regex)
                    else:
                        series_entry[series_name]["name_regexp"] = [series_regex]
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
