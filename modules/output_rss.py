import logging
import datetime
import operator
import os
from manager import ModuleWarning

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
        manager.register('make_rss')

    def validator(self):
        """Validate given configuration"""
        import validator
        root = validator.factory()
        root.accept('text') # TODO: path / file
        rss = root.accept('dict')
        rss.accept('text', key='file', required=True)
        rss.accept('number', key='days')
        rss.accept('number', key='items')
        links = rss.accept('list', key='link')
        links.accept('text')
        return root
        
    def get_config(self, feed):
        config = feed.config['make_rss']
        if not isinstance(config, dict):
            config = {'file': config}
        config.setdefault('days', 7)
        config.setdefault('items', -1)
        config.setdefault('link', ['imdb_url', 'input_url'])
        # add url as last resort
        config['link'].append('url')
        return config

    def feed_exit(self, feed):
        """Store finished / downloaded entries at exit"""
        if not rss2gen:
            raise Exception('module make_rss requires PyRSS2Gen library.')
        config = self.get_config(feed)
        store = feed.shared_cache.storedefault(config['file'], [])
        for entry in feed.entries:
            # make rss data item and store it
            rss = {}
            rss['title'] = entry['title']
            for field in config['link']:
                if field in entry:
                    rss['link'] = entry[field]
                    break
            rss['description'] = entry.get('imdb_plot_outline')
            rss['pubDate'] = datetime.datetime.utcnow()
            store.append(rss)

    def application_terminate(self, feed):
        """Write RSS file at application terminate."""
        if not rss2gen:
            return
        # don't generate rss when learning
        if feed.manager.options.learn:
            return

        config = self.get_config(feed)
        if config['file'] in self.written:
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
                             description = 'FlexGet generated RSS feed',
                             lastBuildDate = datetime.datetime.utcnow(),
                             items = rss_items)
        # write rss
        fn = os.path.expanduser(config['file'])
        try:
            rss.write_xml(open(fn, 'w'))
        except IOError:
            # TODO: modules cannot raise ModuleWarnings in terminate event ..
            log.error('Unable to write %s' % fn)
            return
        self.written[config['file']] = True
