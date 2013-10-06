from __future__ import unicode_literals, division, absolute_import
import yaml
from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestInputRSS(FlexGetBase):

    __yaml__ = """
        templates:
          global:
            rss:
              url: rss.xml
              silent: yes
        tasks:
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
          test_all_entries_no:
            rss:
              all_entries: no
          test_all_entries_yes:
            rss:
              all_entries: yes
    """

    def test_rss(self):
        self.execute_task('test')

        # normal entry
        assert self.task.find_entry(title='Normal', url='http://localhost/normal',
                                    description='Description, normal'), \
            'RSS entry missing: normal'

        # multiple enclosures
        assert self.task.find_entry(title='Multiple enclosures', url='http://localhost/enclosure1',
                                    filename='enclosure1', description='Description, multiple'), \
            'RSS entry missing: enclosure1'
        assert self.task.find_entry(title='Multiple enclosures', url='http://localhost/enclosure2',
                                    filename='enclosure2', description='Description, multiple'), \
            'RSS entry missing: enclosure2'
        assert self.task.find_entry(title='Multiple enclosures', url='http://localhost/enclosure3',
                                    filename='enclosure3', description='Description, multiple'), \
            'RSS entry missing: enclosure3'

        # zero sized enclosure should not pick up filename (some idiotic sites)
        e = self.task.find_entry(title='Zero sized enclosure')
        assert e, 'RSS entry missing: zero sized'
        assert not e.has_key('filename'), \
            'RSS entry with 0-sized enclosure should not have explicit filename'

        # messy enclosure
        e = self.task.find_entry(title='Messy enclosure')
        assert e, 'RSS entry missing: messy'
        assert e.has_key('filename'), 'Messy RSS enclosure: missing filename'
        assert e['filename'] == 'enclosure.mp3', 'Messy RSS enclosure: wrong filename'

        # pick link from guid
        assert self.task.find_entry(title='Guid link', url='http://localhost/guid',
                                    description='Description, guid'), \
                                    'RSS entry missing: guid'

        # empty title, should be skipped
        assert not self.task.find_entry(description='Description, empty title'), \
            'RSS entry without title should be skipped'

    def test_rss2(self):
        # custom link field
        self.execute_task('test2')
        assert self.task.find_entry(title='Guid link', url='http://localhost/otherlink'), \
            'Custom field link not found'

    def test_rss3(self):
        # grab other_fields and attach to entry
        self.execute_task('test3')
        for entry in self.task.rejected:
            print entry['title']
        assert self.task.find_entry(title='Other fields', otherfield='otherfield'), \
            'Specified other_field not attached to entry'

    def test_group_links(self):
        self.execute_task('test_group_links')
        # Test the composite entry was made
        entry = self.task.find_entry(title='Multiple enclosures', url='http://localhost/multiple_enclosures')
        assert entry, 'Entry not created for item with multiple enclosures'
        urls = ['http://localhost/enclosure%d' % num for num in range(1, 3)]
        urls_not_present = [url for url in urls if url not in entry.get('urls')]
        assert not urls_not_present, '%s should be present in urls list' % urls_not_present
        # Test no entries were made for the enclosures
        for url in urls:
            assert not self.task.find_entry(title='Multiple enclosures', url=url), \
                'Should not have created an entry for each enclosure'

    def test_multiple_links(self):
        self.execute_task('test_multiple_links')
        entry = self.task.find_entry(title='Guid link', url='http://localhost/guid',
                                    description='Description, guid')
        assert entry['urls'] == ['http://localhost/guid', 'http://localhost/otherlink'], \
            'Failed to set urls with both links'

    def test_all_entries_no(self):
        self.execute_task('test_all_entries_no')
        assert self.task.entries, 'Entries should have been produced on first run.'
        # reset input cache so that the cache is not used for second execution
        from flexget.utils.cached_input import cached
        cached.cache.clear()
        self.execute_task('test_all_entries_no')
        assert not self.task.entries, 'No entries should have been produced the second run.'

    def test_all_entries_yes(self):
        self.execute_task('test_all_entries_yes')
        assert self.task.entries, 'Entries should have been produced on first run.'
        self.execute_task('test_all_entries_yes')
        assert self.task.entries, 'Entries should have been produced on second run.'


class TestRssOnline(FlexGetBase):

    __yaml__ = """
        tasks:
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
        # Make sure entries are created for all test tasks
        tasks = yaml.load(self.__yaml__)['tasks']
        for task in tasks:
            self.execute_task(task)
            assert self.task.entries, 'No results for task `%s`' % task
