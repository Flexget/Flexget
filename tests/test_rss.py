from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest
import yaml


class TestInputRSS(object):
    config = """
        tasks:
          _:
            rss: &rss
              url: rss.xml
              silent: yes
          test:
            rss: *rss
          test2:
            rss:
              <<: *rss
              link: otherlink
          test3:
            rss:
              <<: *rss
              other_fields: ['Otherfield']
          test_group_links:
            rss:
              <<: *rss
              group_links: yes
          test_multiple_links:
            rss:
              <<: *rss
              link:
                - guid
                - otherlink
          test_all_entries_no:
            rss:
              <<: *rss
              all_entries: no
          test_all_entries_yes:
            rss:
              <<: *rss
              all_entries: yes
          test_field_sanitation:
            rss:
              <<: *rss
              link: "other:link"
              title: "other:Title"
              other_fields:
              - "Other:field"
    """

    def test_rss(self, execute_task):
        task = execute_task('test')

        # normal entry
        assert task.find_entry(title='Normal', url='http://localhost/normal',
                               description='Description, normal'), \
            'RSS entry missing: normal'

        # multiple enclosures
        assert task.find_entry(title='Multiple enclosures', url='http://localhost/enclosure1',
                               filename='enclosure1', description='Description, multiple'), \
            'RSS entry missing: enclosure1'
        assert task.find_entry(title='Multiple enclosures', url='http://localhost/enclosure2',
                               filename='enclosure2', description='Description, multiple'), \
            'RSS entry missing: enclosure2'
        assert task.find_entry(title='Multiple enclosures', url='http://localhost/enclosure3',
                               filename='enclosure3', description='Description, multiple'), \
            'RSS entry missing: enclosure3'

        # zero sized enclosure should not pick up filename (some idiotic sites)
        e = task.find_entry(title='Zero sized enclosure')
        assert e, 'RSS entry missing: zero sized'
        assert 'filename' not in e, \
            'RSS entry with 0-sized enclosure should not have explicit filename'

        # messy enclosure
        e = task.find_entry(title='Messy enclosure')
        assert e, 'RSS entry missing: messy'
        assert 'filename' in e, 'Messy RSS enclosure: missing filename'
        assert e['filename'] == 'enclosure.mp3', 'Messy RSS enclosure: wrong filename'

        # pick link from guid
        assert task.find_entry(title='Guid link', url='http://localhost/guid',
                               description='Description, guid'), \
            'RSS entry missing: guid'

        # empty title, should be skipped
        assert not task.find_entry(description='Description, empty title'), \
            'RSS entry without title should be skipped'

    def test_rss2(self, execute_task):
        # custom link field
        task = execute_task('test2')
        assert task.find_entry(title='Guid link', url='http://localhost/otherlink'), \
            'Custom field link not found'

    def test_rss3(self, execute_task):
        # grab other_fields and attach to entry
        task = execute_task('test3')
        for entry in task.rejected:
            print(entry['title'])
        assert task.find_entry(title='Other fields', otherfield='otherfield'), \
            'Specified other_field not attached to entry'

    def test_group_links(self, execute_task):
        task = execute_task('test_group_links')
        # Test the composite entry was made
        entry = task.find_entry(title='Multiple enclosures', url='http://localhost/multiple_enclosures')
        assert entry, 'Entry not created for item with multiple enclosures'
        urls = ['http://localhost/enclosure%d' % num for num in range(1, 3)]
        urls_not_present = [url for url in urls if url not in entry.get('urls')]
        assert not urls_not_present, '%s should be present in urls list' % urls_not_present
        # Test no entries were made for the enclosures
        for url in urls:
            assert not task.find_entry(title='Multiple enclosures', url=url), \
                'Should not have created an entry for each enclosure'

    def test_multiple_links(self, execute_task):
        task = execute_task('test_multiple_links')
        entry = task.find_entry(title='Guid link', url='http://localhost/guid',
                                description='Description, guid')
        assert entry['urls'] == ['http://localhost/guid', 'http://localhost/otherlink'], \
            'Failed to set urls with both links'

    def test_all_entries_no(self, execute_task):
        task = execute_task('test_all_entries_no')
        assert task.entries, 'Entries should have been produced on first run.'
        # reset input cache so that the cache is not used for second execution
        from flexget.utils.cached_input import cached
        cached.cache.clear()
        task = execute_task('test_all_entries_no')
        assert not task.entries, 'No entries should have been produced the second run.'

    def test_all_entries_yes(self, execute_task):
        task = execute_task('test_all_entries_yes')
        assert task.entries, 'Entries should have been produced on first run.'
        task = execute_task('test_all_entries_yes')
        assert task.entries, 'Entries should have been produced on second run.'

    def test_field_sanitation(self, execute_task):
        task = execute_task('test_field_sanitation')
        entry = task.entries[0]
        assert entry['title'] == 'alt title'
        assert entry['url'] == 'http://localhost/altlink'
        assert entry['other:field'] == 'otherfield'


@pytest.mark.online
class TestRssOnline(object):
    config = """
        tasks:
          normal:
            rss: http://labs.silverorange.com/local/solabs/rsstest/rss_plain.xml

          ssl_no_http_auth:
            rss: https://www.nasa.gov/rss/dyn/breaking_news.rss

          auth_no_ssl:
            rss:
              url: http://labs.silverorange.com/local/solabs/rsstest/httpauth/rss_with_auth.xml
              username: testuser
              password: testpass

          # This test fails because their SSL certificate has expired (dumbasses). Should be safe to ignore.
          #ssl_auth:
          #  rss:
          #    url: https://secure3.silverorange.com/rsstest/httpauth/rss_with_ssl_and_auth.xml
          #    username: testuser
          #    password: testpass

    """

    def test_rss_online(self, execute_task, use_vcr):
        # Make sure entries are created for all test tasks
        tasks = yaml.load(self.config)['tasks']
        for task in tasks:
            task = execute_task(task)
            assert task.entries, 'No results for task `%s`' % task
