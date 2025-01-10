import pytest
from jinja2 import Template


class TestExistsMovie:
    _config = """
        templates:
          global:
            parsing:
              movie: {{parser}}
        tasks:
          test_dirs:
            mock:
              - {title: 'Existence.2012'}
              - {title: 'The.Missing.2014'}
            accept_all: yes
            exists_movie:
              path: __tmp__

          test_files:
            mock:
              - {title: 'Duplicity.2009'}
              - {title: 'Downloaded.2013'}
              - {title: 'Gone.Missing.2013'}
            accept_all: yes
            exists_movie:
              path: __tmp__
              type: files

          test_same_name_diff_year:
            mock:
              - {title: 'Downloaded.2013'}
              - {title: 'Downloaded.2019'}
              - {title: 'Downloaded'}
            accept_all: yes
            exists_movie:
              path: __tmp__
              type: files

          test_lookup_imdb:
            mock:
              - {title: 'Existence.2012'}
              - {title: 'The.Matrix.1999'}
            accept_all: yes
            exists_movie:
              path: __tmp__
              lookup: imdb

          test_diff_qualities_allowed:
            mock:
              - {title: 'Quality.of.Life.480p'}
              - {title: 'Quality.of.Life.1080p'}
              - {title: 'Quality.of.Life.720p'}
            accept_all: yes
            exists_movie:
              path:  __tmp__
              allow_different_qualities: yes

          test_diff_qualities_not_allowed:
            mock:
              - {title: 'Quality.of.Life.1080p'}
            accept_all: yes
            exists_movie: __tmp__

          test_diff_qualities_downgrade:
            mock:
              - {title: 'Quality.of.Life.480p'}
              - {title: 'Quality.of.Life.576p'}
            accept_all: yes
            exists_movie:
              path:  __tmp__
              allow_different_qualities: better

          test_diff_qualities_upgrade:
            mock:
              - {title: 'Quality.of.Life.1080p'}
            accept_all: yes
            exists_movie:
              path:  __tmp__
              allow_different_qualities: better

          test_propers:
            mock:
              - {title: 'Mock.S01E01.Proper'}
              - {title: 'Test.S01E01'}
            accept_all: yes
            exists_movie: __tmp__

          test_invalid:
            mock:
              - {title: 'Invalid.S01E01'}
            accept_all: yes
            exists_movie: __tmp__
    """

    test_files = ['Downloaded.2013.mkv', 'Invalid.jpg']
    test_dirs = ['Existence.2012', 'Quality.of.Life.720p', 'Quality.of.Life.xvid.540p', 'Subs']

    @pytest.fixture(params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request, tmp_path):
        """Override and parametrize default config fixture for all series tests."""
        for test_dir in self.test_dirs:
            tmp_path.joinpath(test_dir).mkdir()
        # create test files
        for test_file in self.test_files:
            tmp_path.joinpath(test_file).write_text('')
        return (
            Template(self._config)
            .render({'parser': request.param})
            .replace('__tmp__', tmp_path.as_posix())
        )

    def test_existing_dirs(self, execute_task):
        """exists_movie plugin: existing"""
        task = execute_task('test_dirs')
        assert not task.find_entry('accepted', title='Existence.2012'), (
            'Existence.2012 should not have been accepted (exists)'
        )
        assert task.find_entry('accepted', title='The.Missing.2014'), (
            'The.Missing.2014 should have been accepted'
        )

    def test_existing_files(self, execute_task):
        """exists_movie plugin: existing"""
        task = execute_task('test_files')
        assert not task.find_entry('accepted', title='Downloaded.2013'), (
            'Downloaded.2013 should not have been accepted (exists)'
        )
        assert task.find_entry('accepted', title='Gone.Missing.2013'), (
            'Gone.Missing.2013 should have been accepted'
        )

    def test_same_name_diff_year(self, execute_task):
        """exists_movie plugin: existing with same name with different year"""
        task = execute_task('test_same_name_diff_year')
        assert not task.find_entry('accepted', title='Downloaded.2013'), (
            'Downloaded.2013 should not have been accepted (exists)'
        )
        assert task.find_entry('accepted', title='Downloaded'), (
            'Downloaded should have been accepted'
        )
        assert task.find_entry('accepted', title='Downloaded.2019'), (
            'Downloaded.2019 should have been accepted'
        )

    @pytest.mark.online
    def test_lookup_imdb(self, execute_task):
        """exists_movie plugin: existing"""
        task = execute_task('test_lookup_imdb')
        assert task.find_entry('accepted', title='The.Matrix.1999')['imdb_id'], (
            'The.Matrix.1999 should have an `imdb_id`'
        )
        assert not task.find_entry('accepted', title='Existence.2012'), (
            'Existence.2012 should not have been accepted (exists)'
        )

    def test_diff_qualities_allowed(self, execute_task):
        """exists_movie plugin: existsting but w. diff quality"""
        task = execute_task('test_diff_qualities_allowed')
        assert task.find_entry('accepted', title='Quality.of.Life.480p'), (
            'Quality.of.Life.480p should have been accepted'
        )
        assert task.find_entry('accepted', title='Quality.of.Life.1080p'), (
            'Quality.of.Life.1080p should have been accepted'
        )
        assert task.find_entry('rejected', title='Quality.of.Life.720p'), (
            'Quality.of.Life.720p should have been rejected'
        )

    def test_diff_qualities_not_allowed(self, execute_task):
        """exists_movie plugin: existsting but w. diff quality"""
        task = execute_task('test_diff_qualities_not_allowed')
        assert task.find_entry('rejected', title='Quality.of.Life.1080p'), (
            'Quality.of.Life.1080p should have been rejected'
        )

    def test_diff_qualities_downgrade(self, execute_task):
        """Test worse qualities than exist are rejected."""
        task = execute_task('test_diff_qualities_downgrade')
        assert task.find_entry('rejected', title='Quality.of.Life.480p'), (
            'Quality.of.Life.480p should have been rejected'
        )
        assert task.find_entry('rejected', title='Quality.of.Life.576p'), (
            'Quality.of.Life.576p should have been rejected'
        )

    def test_diff_qualities_upgrade(self, execute_task):
        """Test better qualities than exist are accepted."""
        task = execute_task('test_diff_qualities_upgrade')
        assert task.find_entry('accepted', title='Quality.of.Life.1080p'), (
            'Quality.of.Life.1080p should have been accepted'
        )

    # TODO: Fix tests
    @pytest.mark.skip(reason='test is broken')
    def test_propers(self, execute_task):
        """exists_movie plugin: new proper & proper already exists"""
        task = execute_task('test_propers')
        assert task.find_entry('accepted', title='Mock.S01E01.Proper'), 'new proper not accepted'
        assert task.find_entry('rejected', title='Test.S01E01'), (
            'pre-existin proper should have caused reject'
        )

    def test_invalid(self, execute_task):
        """exists_movie plugin: no episode numbering on the disk"""
        execute_task('test_invalid')

    @pytest.mark.skip(reason='test is broken')
    def test_with_metainfo_series(self, execute_task):
        """Tests that exists_movie works with series data from metainfo_series"""
        task = execute_task('test_with_metainfo_series')
        assert task.find_entry('rejected', title='Foo.Bar.S01E02.XViD'), (
            'Foo.Bar.S01E02.XViD should have been rejected(exists)'
        )
        assert not task.find_entry('rejected', title='Foo.Bar.S01E03.XViD'), (
            'Foo.Bar.S01E03.XViD should not have been rejected'
        )
