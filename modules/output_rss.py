import logging
import datetime

log = logging.getLogger('make_rss')

rss2gen = True
try:
    import PyRSS2Gen
except:
    rss2gen = False

class OutputRSS:

    """
        Write RSS containing succeeded (downloaded) entries.
        
        Example:
        
        make_rss: ~/public_html/flexget.rss
        
        You may write into same file in multiple feeds.
        
        Example:
        
        my-feed-A:
          make_rss: ~/public_html/series.rss
          .
          .
        my-feed-B:
          make_rss: ~/public_html/series.rss
          .
          .
          
        With this example file series.rss would contain succeeded
        entries from both feeds.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='exit', keyword='make_rss', callback=self.store_entries)
        manager.register(instance=self, event='terminate', keyword='make_rss', callback=self.write_rss)

    def store_entries(self, feed):
        if not rss2gen:
            raise Exception('module make_rss requires PyRSS2Gen library.')
        filename = feed.config['make_rss']
        store = feed.shared_cache.storedefault(filename, [])
        for entry in feed.entries:
            # make rss data item and store it
            rss = {}
            rss['title'] = entry['title']
            rss['link'] = entry['url']
            rss['description'] = entry.get('imdb_plot_outline')
            rss['pubDate'] = datetime.datetime.utcnow()
            store.append(rss)

    def write_rss(self, feed):
        if not rss2gen:
            return
        filename = feed.config['make_rss']
        data_items = feed.shared_cache.get(filename)

        # make items
        rss_items = []
        for data_item in data_items:
            rss_item = PyRSS2Gen.RSSItem(**data_item)
            rss_items.append(rss_item)
            
        rss_items.reverse()

        # make rss
        rss = PyRSS2Gen.RSS2(title = 'FlexGet',
                             link = None,
                             description = "FlexGet generated RSS feed",
                             lastBuildDate = datetime.datetime.utcnow(),
                             items = rss_items)
        # write rss
        rss.write_xml(open(filename, "w"))
