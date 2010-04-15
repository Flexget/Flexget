from tests import FlexGetBase


class TestPreset(FlexGetBase):
    __yaml__ = """
        presets:
          global:
            mock:
              - {title: 'global'}
          movies:
            mock:
              - {title: 'movies'}

        feeds:
          test1:
            preset: movies

          test2:
            preset: no

          test3:
            preset:
              - movies
              - no_global
    """

    def test_preset1(self):
        self.execute_feed('test1')
        assert self.feed.find_entry(title='global'), 'test1, preset global not applied'
        assert self.feed.find_entry(title='movies'), 'test1, preset movies not applied'

    def test_preset2(self):
        self.execute_feed('test2')
        assert not self.feed.find_entry(title='global'), 'test2, preset global applied'
        assert not self.feed.find_entry(title='movies'), 'test2, preset movies applied'

    def test_preset3(self):
        self.execute_feed('test3')
        assert not self.feed.find_entry(title='global'), 'test3, preset global applied'
        assert self.feed.find_entry(title='movies'), 'test3, preset movies not applied'


class TestPresetMerge(FlexGetBase):

    __yaml__ = """
        presets:
          movies:
            seen_movies: strict
            imdb:
              min_score: 6.0
              min_votes: 500
              min_year: 2006
              reject_genres:
                - musical
                - music
                - biography
                - romance

        feeds:
          test:
            preset: movies
            imdb:
              min_score: 6.5
              reject_genres:
                - comedy
    """

    def test_merge(self):
        self.execute_feed('test')
        assert self.feed.config['imdb']['min_score'] == 6.5, 'float merge failed'
        assert 'comedy' in self.feed.config['imdb']['reject_genres'], 'list merge failed'
