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
        root.accept('text', key='series_group')
        return root

    @internet(log)
    def on_process_start(self, feed):
        config = feed.config.get('thetvdb_favorites')
        url = "http://thetvdb.com/api/User_Favorites.php?accountid=%s" % str(config['account_id'])
        data = BeautifulStoneSoup(urllib.urlopen(url))
        favorite_ids = []
        for i in data.favorites.findAll("series", recursive=False):
            favorite_ids.append(int(i.string))
        if not favorite_ids:
            log.info("Didn't find any thetvdb.com favorites.")
            return
        tvdb_series_config = {}
        series_group = config.get('series_group', 'thetvdb_favs')
        tvdb_series_config[series_group] = []
        for fid in favorite_ids:
            data = BeautifulStoneSoup(urllib.urlopen("http://thetvdb.com/data/series/%s/" % str(fid)))
            tvdb_series_config[series_group].append(data.series.seriesname.string)
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
