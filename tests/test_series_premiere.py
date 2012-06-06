from tests import FlexGetBase


class TestSeriesPremiere(FlexGetBase):

    __yaml__ = """

        presets:
          global: # just cleans log a bit ..
            disable_builtins:
              - seen

        feeds:
          test_only_one:
            mock:
              - {title: 'Foo.2009.S01E01.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo 2009 S01E01 HDTV XviD-2HD[ASDF]'}
              - {title: 'Foo (2009) S01E01HDTV XviD-2HD[AOEU]'}
              - {title: 'Foo 2009 S01E02 HDTV Xvid-2HD[AOEU]'}
            series_premiere: yes

          test_dupes_across_feeds_1:
            mock:
              - {title: 'Foo.Bar.S01E01.HDTV.XviD-2HD[FlexGet]'}
            series_premiere: yes

          test_dupes_across_feeds_2:
            mock:
              - {title: 'foo bar s01e01 dsr xvid-2hd[dmg]'}
            series_premiere: yes
          test_path_set:
            mock:
              - {title: 'foo bar s01e01 hdtv'}
            series_premiere:
              path: test
          test_pilot_and_premiere:
            mock:
              - {title: 'foo bar s01e00 hdtv'}
              - {title: 'foo bar s01e01 hdtv'}
            series_premiere: yes
          test_multi_episode:
            mock:
              - {title: 'foo bar s01e01e02 hdtv'}
            series_premiere: yes
    """

    def test_only_one(self):
        self.execute_feed('test_only_one')
        assert len(self.feed.accepted) == 1, 'should only have accepted one'

    def test_dupes_across_feeds(self):
        self.execute_feed('test_dupes_across_feeds_1')
        assert len(self.feed.accepted) == 1, 'didn\'t accept first premiere'
        self.execute_feed('test_dupes_across_feeds_2')
        assert len(self.feed.accepted) == 0, 'accepted duplicate premiere'

    def test_path_set(self):
        self.execute_feed('test_path_set')
        assert self.feed.find_entry(title='foo bar s01e01 hdtv', path='test')

    def test_pilot_and_premiere(self):
        self.execute_feed('test_pilot_and_premiere')
        assert len(self.feed.accepted) == 2, 'should have accepted pilot and premiere'

    def test_multi_episode(self):
        self.execute_feed('test_multi_episode')
        assert len(self.feed.accepted) == 1, 'should have accepted multi-episode premiere'
