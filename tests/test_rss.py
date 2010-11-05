from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestInputRSS(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            rss: 
              url: tests/rss.xml
              silent: true
          test2:
            rss:
              url: tests/rss.xml
              silent: true
              link: otherlink
          test3:
            rss:
              url: tests/rss.xml
              silent: true
              other_fields: ['Otherfield']
    """
    
    def test_rss(self):
        self.execute_feed('test')

        # normal entry
        assert self.feed.find_entry(title='Normal', url='http://localhost/normal', \
                                    description='Description, normal'), \
            'RSS entry missing: normal'
        
        # multiple enclosures
        assert self.feed.find_entry(title='Multiple enclosures', url='http://localhost/enclosure1', \
                                    filename='enclosure1', description='Description, multiple'), \
            'RSS entry missing: enclosure1'
        assert self.feed.find_entry(title='Multiple enclosures', url='http://localhost/enclosure2', \
                                    filename='enclosure2', description='Description, multiple'), \
            'RSS entry missing: enclosure2'
        assert self.feed.find_entry(title='Multiple enclosures', url='http://localhost/enclosure3', \
                                    filename='enclosure3', description='Description, multiple'), \
            'RSS entry missing: enclosure3'
        
        # zero sized enclosure should not pick up filename (some idiotic sites)
        e = self.feed.find_entry(title='Zero sized enclosure')
        assert e, 'RSS entry missing: zero sized'
        assert not e.has_key('filename'), \
            'RSS entry with 0-sized enclosure should not have explicit filename'
        
        # messy enclosure
        e = self.feed.find_entry(title='Messy enclosure')
        assert e, 'RSS entry missing: messy'
        assert e.has_key('filename'), 'Messy RSS enclosure: missing filename'
        assert e['filename'] == 'enclosure.mp3', 'Messy RSS enclosure: wrong filename'
        
        # pick link from guid
        assert self.feed.find_entry(title='Guid link', url='http://localhost/guid', \
                                    description='Description, guid'), \
                                    'RSS entry missing: guid'
            
        # empty title, should be skipped
        assert not self.feed.find_entry(description='Description, empty title'), \
            'RSS entry without title should be skipped'

    def test_rss2(self):
        # reset input cache so that the cache is not used for second execution
        from flexget.plugins.cached_input import cached
        cached.cache = {}
        # custom link field
        self.execute_feed('test2')
        assert self.feed.find_entry(title='Guid link', url='http://localhost/otherlink'), \
            'Custom field link not found'

    def test_rss3(self):
        # reset input cache so that the cache is not used for second execution
        from flexget.plugins.cached_input import cached
        cached.cache = {}
        # grab other_fields and attach to entry
        self.execute_feed('test3')
        for entry in self.feed.rejected:
            print entry['title']
        assert self.feed.find_entry(title='Other fields', otherfield='otherfield'), \
            'Specified other_field not attached to entry'


class TestRssOnline(FlexGetBase):
    
    __yaml__ = """
        feeds:
          normal:
            rss: http://labs.silverorange.com/local/solabs/rsstest/rss_plain.xml

          ssl_no_http_auth:
            rss: https://secure3.silverorange.com/rsstest/rss_with_ssl.xml

          auth_no_ssl:
            rss: 
              url: http://labs.silverorange.com/local/solabs/rsstest/httpauth/rss_with_auth.xml
              username: testuser
              password: testpass

          ssl_auth:
            rss: 
              url: https://secure3.silverorange.com/rsstest/httpauth/rss_with_ssl_and_auth.xml
              username: testuser
              password: testpass
    """
    
    @attr(online=True)
    def test_rss_online(self):
        # TODO: XXX
        pass
