import logging
import datetime
import os
from flexget.plugin import register_plugin, PluginWarning
from flexget.manager import Base
from sqlalchemy import Column, Integer, String, DateTime

log = logging.getLogger('make_rss')

rss2gen = True
try:
    import PyRSS2Gen
except:
    rss2gen = False


class RSSEntry(Base):

    __tablename__ = 'make_rss'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    link = Column(String)
    rsslink = Column(String)
    file = Column(String)
    published = Column(DateTime, default=datetime.datetime.utcnow())


class OutputRSS(object):
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

        RSS location link:

        You can specify the url location of the rss file.

        Example:

        make_rss:
          file: ~/public_html/series.rss
          rsslink: http://my.server.net/series.rss

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

    def validator(self):
        """Validate given configuration"""
        from flexget import validator
        root = validator.factory()
        root.accept('text') # TODO: path / file
        rss = root.accept('dict')
        rss.accept('text', key='file', required=True)
        rss.accept('number', key='days')
        rss.accept('number', key='items')
        rss.accept('boolean', key='history')
        rss.accept('text', key='rsslink')
        rss.accept('text', key='encoding') # TODO: only valid choices
        links = rss.accept('list', key='link')
        links.accept('text')
        return root

    def on_feed_output(self, feed):
        # makes this plugin count as output (stops warnings about missing outputs)
        pass

    def get_config(self, feed):
        config = feed.config['make_rss']
        if not isinstance(config, dict):
            config = {'file': config}
        config.setdefault('days', 7)
        config.setdefault('items', -1)
        config.setdefault('history', True)
        config.setdefault('encoding', 'iso-8859-1')
        config.setdefault('link', ['imdb_url', 'input_url'])
        # add url as last resort
        config['link'].append('url')
        return config

    def on_feed_exit(self, feed):
        """Store finished / downloaded entries at exit"""
        if not rss2gen:
            raise PluginWarning('plugin make_rss requires PyRSS2Gen library.')
        config = self.get_config(feed)

        # don't run with --test
        if feed.manager.options.test:
            return

        # when history is disabled, remove everything from backlog on every run (a bit hackish, rarely usefull)
        if not config['history']:
            log.debug('disabling history')
            for item in feed.session.query(RSSEntry).filter(RSSEntry.file == config['file']).all():
                feed.session.delete(item)

        # save entries into db for RSS generation
        for entry in feed.accepted:
            rss = RSSEntry()
            rss.title = entry['title']
            for field in config['link']:
                if field in entry:
                    rss.link = entry[field]
                    break

            # TODO: just a quick hack, implement better :)
            description = ''
            if 'imdb_score' in entry:
                description += 'Score: %s / 10 | ' % entry['imdb_score']
            if 'imdb_votes' in entry:
                description += 'Votes: %s | ' % entry['imdb_votes']
            if 'imdb_genres' in entry:
                description += 'Genres: %s | ' % ', '.join(entry['imdb_genres'])
            if 'imdb_plot_outline' in entry:
                description += 'Description: %s' % entry['imdb_plot_outline']
            else:
                description += entry.get('description', '')

            rss.description = description
            rss.file = config['file']

            # TODO: check if this exists and suggest disabling history if it does since it shouldn't happen normally ...
            log.debug('Saving %s into rss database' % entry['title'])
            feed.session.add(rss)

    def on_process_end(self, feed):
        """Write RSS file at application terminate."""
        if not rss2gen:
            return
        # don't generate rss when learning
        if feed.manager.options.learn:
            return

        config = self.get_config(feed)
        if config['file'] in self.written:
            log.log(5, 'skipping already written file %s' % config['file'])
            return

        # in terminate phase there is no open session in feed, so open new one
        from flexget.manager import Session
        session = Session()

        db_items = session.query(RSSEntry).filter(RSSEntry.file == config['file']).\
            order_by(RSSEntry.published.desc()).all()

        # make items
        rss_items = []
        for db_item in db_items:
            add = True
            if config['items'] != -1:
                if len(rss_items) > config['items']:
                    add = False
            if config['days'] != -1:
                if datetime.datetime.today() - datetime.timedelta(days=config['days']) > db_item.published:
                    add = False
            if add:
                # add into generated feed
                gen = {}
                gen['title'] = db_item.title
                gen['description'] = db_item.description
                gen['link'] = db_item.link
                gen['pubDate'] = db_item.published
                log.log(5, 'Adding %s into rss %s' % (gen['title'], config['file']))
                rss_items.append(PyRSS2Gen.RSSItem(**gen))
            else:
                # no longer needed
                session.delete(db_item)

        session.commit()
        session.close()

        # make rss
        rss = PyRSS2Gen.RSS2(title='FlexGet',
                             link=config.get('rsslink', 'http://flexget.com'),
                             description='FlexGet generated RSS feed',
                             lastBuildDate=datetime.datetime.utcnow(),
                             items=rss_items)
        # write rss
        fn = os.path.expanduser(config['file'])
        try:
            rss.write_xml(open(fn, 'w'), encoding=config['encoding'])
        except LookupError:
            log.critical('Unknown encoding %s' % config['encoding'])
            return
        except IOError:
            # TODO: plugins cannot raise PluginWarnings in terminate event ..
            log.critical('Unable to write %s' % fn)
            return
        self.written[config['file']] = True


register_plugin(OutputRSS, 'make_rss')
