import logging
from flexget.plugin import *
from BeautifulSoup import BeautifulStoneSoup
import urllib

log = logging.getLogger('thetvdb_favorites')


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
        root.accept('text', key='account_id')
        return root

    def on_process_start(self, feed):
        config = feed.config.get('thetvdb_favorites')
        url = "http://thetvdb.com/api/User_Favorites.php?accountid=%s" % str(config['account_id'])
        data = BeautifulStoneSoup(urllib.urlopen(url))
        favorite_ids = []
        for i in data.favorites.findAll("series", recursive=False):
            favorite_ids.append(int(i.string))
        tvdb_series_config = {}
        tvdb_series_config['thetvdb_favorites'] = []
        for fid in favorite_ids:
            data = BeautifulStoneSoup(urllib.urlopen("http://thetvdb.com/data/series/%s/" % str(fid)))
            tvdb_series_config['thetvdb_favorites'].append(data.series.seriesname.string)
        # If the series plugin is not configured on this feed, make a blank config
        if not 'series' in feed.config:
            feed.config['series'] = {}
        # Merge the tvdb shows in to the main series config
        from flexget.utils.tools import MergeException, merge_dict_from_to
        try:
            merge_dict_from_to(tvdb_series_config, feed.config['series'])
        except MergeException:
            raise PluginError('Failed to merge thetvdb favorites to feed %s, incompatible datatypes' % feed.name)


register_plugin(FilterThetvdbFavorites, 'thetvdb_favorites')
