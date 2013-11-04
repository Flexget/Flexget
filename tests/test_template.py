from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestTemplate(FlexGetBase):
    __yaml__ = """
        templates:
          global:
            mock:
              - {title: 'global'}
          movies:
            mock:
              - {title: 'movies'}
          a:
            mock:
              - {title: 'a'}
            template: b
          b:
            mock:
              - {title: 'b'}

        tasks:
          test1:
            template: movies

          test2:
            template: no

          test3:
            template:
              - movies
              - no_global

          test_nested:
            template:
              - a
              - no_global
    """

    def test_preset1(self):
        self.execute_task('test1')
        assert self.task.find_entry(title='global'), 'test1, preset global not applied'
        assert self.task.find_entry(title='movies'), 'test1, preset movies not applied'

    def test_preset2(self):
        self.execute_task('test2')
        assert not self.task.find_entry(title='global'), 'test2, preset global applied'
        assert not self.task.find_entry(title='movies'), 'test2, preset movies applied'

    def test_preset3(self):
        self.execute_task('test3')
        assert not self.task.find_entry(title='global'), 'test3, preset global applied'
        assert self.task.find_entry(title='movies'), 'test3, preset movies not applied'

    def test_nested(self):
        self.execute_task('test_nested')
        assert self.task.find_entry(title='a'), 'Entry from preset a was not created'
        assert self.task.find_entry(title='b'), 'Entry from preset b was not created'
        assert len(self.task.entries) == 2, 'Should only have been 2 entries created'


class TestTemplateMerge(FlexGetBase):

    __yaml__ = """
        templates:
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

        tasks:
          test:
            template: movies
            imdb:
              min_score: 6.5
              reject_genres:
                - comedy
    """

    def test_merge(self):
        self.execute_task('test')
        assert self.task.config['imdb']['min_score'] == 6.5, 'float merge failed'
        assert 'comedy' in self.task.config['imdb']['reject_genres'], 'list merge failed'


class TestTemplateRerun(FlexGetBase):
    __yaml__ = """
        templates:
          a:
            series:
            - someseries
        tasks:
          test_rerun:
            template: a
            rerun: 1
    """

    def test_rerun(self):
        self.execute_task('test_rerun')
        assert len(self.task.config['series']) == 1
