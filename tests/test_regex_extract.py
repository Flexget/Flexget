from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestRegexExtract(FlexGetBase):
    __yaml__ = """
        tasks:

          test_1:
            mock:
              - {title: 'The.Event.New.York'}
            regex_extract:
              prefix: event_
              field: title
              regex:
                - The\.Event\.(?P<location>.*)

          test_2:
            mock:
              - {title: 'TheShow.Detroit'}
            regex_extract:
              prefix: event_
              field: title
              regex:
                - The\.Event\.(?P<location>.*)

          test_3:
            mock:
              - {title: 'The.Event.New.York'}
            regex_extract:
              field: title
              regex:
                - The\.Event\.(?P<location>.*)

          test_4:
            mock:
              - {title: 'The.Event.New.York.2015'}
            regex_extract:
              prefix: event_
              field: title
              regex:
                - The\.Event\.(?P<location>[\w\.]*?)\.(?P<year>\d{4})

    """

    def test_single_group(self):
        self.execute_task('test_1')
        entry = self.task.find_entry('entries', title='The.Event.New.York')
        assert entry is not None
        assert 'event_location' in entry
        assert entry['event_location'] == 'New.York'

    def test_single_group_non_match(self):
        self.execute_task('test_2')
        entry = self.task.find_entry('entries', title='TheShow.Detroit')
        assert entry is not None
        assert 'event_location' not in entry

    def test_single_group_no_prefix(self):
        self.execute_task('test_3')
        entry = self.task.find_entry('entries', title='The.Event.New.York')
        assert entry is not None
        assert 'location' in entry
        assert entry['location'] == 'New.York'

    def test_multi_group(self):
        self.execute_task('test_4')
        entry = self.task.find_entry('entries', title='The.Event.New.York.2015')
        assert entry is not None
        assert 'event_location' in entry
        assert 'event_year' in entry
        assert entry['event_location'] == 'New.York'
        assert entry['event_year'] == '2015'
