import logging
import datetime
import types
import operator

__pychecker__ = 'unusednames=parser'

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
        
        Number of days / items:
        -----------------------
        
        By default output contains items from last 7 days. You can specify
        different perioid, number of items or both. Value -1 means unlimited.
        
        Example:
        
        make_rss:
          file: ~/public_html/series.rss
          days: 2
          items: 10
          
        Generate RSS that will containg last two days and no more than 10 items.
        
        Example 2:
        
        make_rss:
          file: ~/public_html/series.rss
          days: -1
          items: 50
          
        Generate RSS that will contain last 50 items, regardless of dates.
        
        RSS link:
        ---------
        
        You can specify what field from entry is used as a link in generated rss feed.
        
        Example:
        
        make_rss:
          file: ~/public_html/series.rss
          link:
            - imdb_url
            
        List should contain a list of fields in order of preference.
        Note that the url field is always used as last possible fallback
        even without explicitly adding it into the list.
        
        Default list: imdb_url, input_url, url
        
    """

    def __init__(self):
        self.written = {}

    def register(self, manager, parser):
        manager.register(event='exit', keyword='make_rss', callback=self.store_entries)
        manager.register(event='terminate', keyword='make_rss', callback=self.write_rss)

    def validate(self, config):
        """Validate given configuration"""
        if isinstance(config, str):
            return []
        from validator import DictValidator
        rss = DictValidator()
        rss.accept('file', str)
        rss.accept('days', int)
        rss.accept('items', int)
        rss.accept('link', list).accept(str)
        rss.validate(config)
        return rss.errors.messages
        
    def get_config(self, feed):
        config = feed.config['make_rss']
        if type(config) != types.DictType:
            config = {'file': config}
        config.setdefault('days', 7)
        config.setdefault('items', -1)
        config.setdefault('link', ['imdb_url', 'input_url'])
        # add url as last resort
        config['link'].append('url')
        if not config.has_key('file'):
            raise Warning('make_rss is missing a file parameter')
        return config

    def store_entries(self, feed):
        if not rss2gen:
            raise Exception('module make_rss requires PyRSS2Gen library.')
        config = self.get_config(feed)
        store = feed.shared_cache.storedefault(config['file'], [])
        for entry in feed.entries:
            # make rss data item and store it
            rss = {}
            rss['title'] = entry['title']
            for field in config['link']:
                if entry.has_key(field):
                    rss['link'] = entry[field]
                    break
            rss['description'] = entry.get('imdb_plot_outline')
            rss['pubDate'] = datetime.datetime.utcnow()
            store.append(rss)

    def write_rss(self, feed):
        if not rss2gen:
            return
        config = self.get_config(feed)
        if self.written.has_key(config['file']):
            log.debug('skipping already written file %s' % config['file'])
            return
        data_items = feed.shared_cache.get(config['file'])

        # sort items by pubDate
        data_items.sort(key=operator.itemgetter('pubDate'))
        data_items.reverse()
          
        # make items
        rss_items = []
        for data_item in data_items[:]:
            add = True
            if config['items'] != -1:
                if len(rss_items) > config['items']:
                    add = False
            if config['days'] != -1:
                if datetime.datetime.today()-datetime.timedelta(days=config['days']) > data_item['pubDate']:
                    add = False
            if add:
                # add into generated feed
                rss_items.append(PyRSS2Gen.RSSItem(**data_item))
            else:
                # purge from storage
                data_items.remove(data_item)

        # make rss
        rss = PyRSS2Gen.RSS2(title = 'FlexGet',
                             link = None,
                             description = "FlexGet generated RSS feed",
                             lastBuildDate = datetime.datetime.utcnow(),
                             items = rss_items)
        # write rss
        rss.write_xml(open(config['file'], "w"))
        self.written[config['file']] = True
