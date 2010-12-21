from tests import FlexGetBase


class TestOnlyNew(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            only_new: yes
            disable_builtins: yes # Disable the seen plugin to make sure only_new does the filtering.
            accept_all: yes

        feeds:
          test:
            mock:
              - {title: 'title 1', url: 'http://localhost/title1'}
    """

    def test_only_new(self):
        self.execute_feed('test')
        assert self.feed.find_entry(title='title 1'), 'Test entry missing'
        # run again, should filter
        self.feed.execute()
        assert not self.feed.find_entry(title='title 1'), 'Seen test entry remains'

        # add another entry to the feed
        self.manager.config['feeds']['test']['mock'].append({'title': 'title 2', 'url': 'http://localhost/title2'})
        # execute again
        self.execute_feed('test')
        # both entries should be present as config has changed
        assert self.feed.find_entry(title='title 1'), 'title 1 was not found'
        assert self.feed.find_entry(title='title 2'), 'title 2 was not found'

        # TODO: Test that new entries are accepted. Tough to do since we can't change the feed name or config..
