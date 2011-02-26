from tests import FlexGetBase


class TestBacklog(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Test.S01E01.hdtv-FlexGet', description: ''}
            set:
              description: '%(description)sI'
              laterfield: 'something'
            backlog: 10 minutes
    """

    def test_backlog(self):
        """Tests backlog (and snapshot) functionality."""

        # Test entry comes out as expected on first run
        self.execute_feed('test')
        entry = self.feed.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == 'I'
        assert entry['laterfield'] == 'something'
        # Simulate entry leaving the feed, make sure backlog injects it
        del(self.feed.config['mock'])
        self.execute_feed('test')
        entry = self.feed.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == 'I'
        assert entry['laterfield'] == 'something'
        # This time take away the set plugin too, to make sure data is being restored at it's state from input
        del(self.feed.config['set'])
        self.execute_feed('test')
        entry = self.feed.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == ''
        assert 'laterfield' not in entry
