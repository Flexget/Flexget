from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestInputRSS(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            rss:
              url: rss.xml
              silent: yes
        feeds:
          test: {}
          test2:
            rss:
              link: otherlink
          test3:
            rss:
              other_fields: ['Otherfield']
          test_group_links:
            rss:
              group_links: yes
          test_multiple_links:
            rss:
              link:
                - guid
                - otherlink

    """

    def setup(self):
        FlexGetBase.setup(self)
        # reset input cache so that the cache is not used for second execution
        from flexget.utils.cached_input import cached
        cached.cache = {}

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
        # custom link field
        self.execute_feed('test2')
        assert self.feed.find_entry(title='Guid link', url='http://localhost/otherlink'), \
            'Custom field link not found'

    def test_rss3(self):
        # grab other_fields and attach to entry
        self.execute_feed('test3')
        for entry in self.feed.rejected:
            print entry['title']
        assert self.feed.find_entry(title='Other fields', otherfield='otherfield'), \
            'Specified other_field not attached to entry'

    def test_group_links(self):
        self.execute_feed('test_group_links')
        # Test the composite entry was made
        entry = self.feed.find_entry(title='Multiple enclosures', url='http://localhost/multiple_enclosures')
        assert entry, 'Entry not created for item with multiple enclosures'
        urls = ['http://localhost/enclosure%d' % num for num in range(1, 3)]
        urls_not_present = [url for url in urls if url not in entry.get('urls')]
        assert not urls_not_present, '%s should be present in urls list' % urls_not_present
        # Test no entries were made for the enclosures
        for url in urls:
            assert not self.feed.find_entry(title='Multiple enclosures', url=url), \
                'Should not have created an entry for each enclosure'

    def test_multiple_links(self):
        self.execute_feed('test_multiple_links')
        entry = self.feed.find_entry(title='Guid link', url='http://localhost/guid', \
                                    description='Description, guid')
        assert entry['urls'] == ['http://localhost/guid', 'http://localhost/otherlink'], \
            'Failed to set urls with both links'


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
