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
    """

    def test_only_one(self):
        self.execute_feed('test_only_one')
        assert len(self.feed.accepted) == 1, 'should only have accepted one'

    def test_dupes_across_feeds(self):
        self.execute_feed('test_dupes_across_feeds_1')
        assert len(self.feed.accepted) == 1, 'didn\'t accept first premiere'
        self.execute_feed('test_dupes_across_feeds_2')
        assert len(self.feed.accepted) == 0, 'accepted duplicate premiere'
