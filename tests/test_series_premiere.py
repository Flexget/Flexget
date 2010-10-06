from tests import FlexGetBase


class TestDuplicates(FlexGetBase):

    __yaml__ = """

        presets:
          global: # just cleans log a bit ..
            disable_builtins:
              - seen

        feeds:
          test_dupes_in_same_feed:
            mock:
              - {title: 'Foo.2009.S01E01.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo.2009.S01E01.HDTV.XviD-2HD[ASDF]'}
            series_premiere: yes

          test_dupes_across_feeds_1:
            mock:
              - {title: 'Foo.Bar.S01E01.HDTV.XviD-2HD[FlexGet]'}
            series_premiere: yes

          test_dupes_across_feeds_2:
            mock:
              - {title: 'Foo.Bar.S01E01.HDTV.XviD-2HD[DMG]'}
            series_premiere: yes
    """

    def test_dupes_in_same_feed(self):
        self.execute_feed('test_dupes_in_same_feed')
        assert len(self.feed.accepted) == 1, 'accepted both'

    def test_dupes_across_feeds(self):
        self.execute_feed('test_dupes_across_feeds_1')
        self.execute_feed('test_dupes_across_feeds_2')
        assert len(self.feed.accepted) == 1, 'accepted both'
