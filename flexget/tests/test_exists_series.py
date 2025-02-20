import os

import pytest


class TestExistsSeries:
    _config = """
        templates:
          global:
            parsing:
              series: __parser__
        tasks:
          test:
            mock:
              - {title: 'Foo.Bar.S01E02.XViD'}
              - {title: 'Foo.Bar.S01E03.XViD'}
            series:
              - foo bar
            exists_series:
              path: __tmp__

          test_diff_qualities_allowed:
            mock:
              - {title: 'Asdf.S01E02.720p'}
            series:
              - asdf
            exists_series:
              path:  __tmp__
              allow_different_qualities: yes

          test_diff_qualities_not_allowed:
            mock:
              - {title: 'Asdf.S01E02.720p'}
            series:
              - asdf
            exists_series: __tmp__

          test_diff_qualities_downgrade:
            mock:
              - {title: 'Asdf.S01E02.sdtv'}
            series:
              - asdf
            exists_series:
              path:  __tmp__
              allow_different_qualities: better

          test_diff_qualities_upgrade:
            mock:
              - {title: 'Asdf.S01E02.webdl'}
            series:
              - asdf
            exists_series:
              path:  __tmp__
              allow_different_qualities: better

          test_propers:
            mock:
              - {title: 'Mock.S01E01.Proper'}
              - {title: 'Test.S01E01'}
            series:
              - mock
              - test
            exists_series: __tmp__

          test_invalid:
            mock:
              - {title: 'Invalid.S01E01'}
            series:
              - invalid
            exists_series: __tmp__

          test_with_metainfo_series:
            metainfo_series: yes
            mock:
              - {title: 'Foo.Bar.S01E02.XViD'}
              - {title: 'Foo.Bar.S01E03.XViD'}
            accept_all: yes
            exists_series: __tmp__
          test_jinja_path:
            series:
            - jinja
            - jinja2
            mock:
            - title: jinja s01e01
            - title: jinja s01e02
            - title: jinja2 s01e01
            accept_all: yes
            exists_series: __tmp__
    """

    test_dirs = [
        'Foo.Bar.S01E02.XViD-GrpA',
        'Asdf.S01E02.HDTV',
        'Mock.S01E01.XViD',
        'Test.S01E01.Proper',
        'jinja/jinja.s01e01',
        'jinja.s01e02',
        'jinja2/jinja2.s01e01',
        'invalid',
    ]

    @pytest.fixture(params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request, tmp_path):
        """Override and parametrize default config fixture for all series tests."""
        for test_dir in self.test_dirs:
            os.makedirs(tmp_path.joinpath(test_dir).as_posix())
        return self._config.replace('__parser__', request.param).replace(
            '__tmp__', tmp_path.as_posix()
        )

    def test_existing(self, execute_task):
        """Exists_series plugin: existing."""
        task = execute_task('test')
        assert not task.find_entry('accepted', title='Foo.Bar.S01E02.XViD'), (
            'Foo.Bar.S01E02.XViD should not have been accepted (exists)'
        )
        assert task.find_entry('accepted', title='Foo.Bar.S01E03.XViD'), (
            'Foo.Bar.S01E03.XViD should have been accepted'
        )

    def test_diff_qualities_allowed(self, execute_task):
        """Exists_series plugin: existsting but w. diff quality."""
        task = execute_task('test_diff_qualities_allowed')
        assert task.find_entry('accepted', title='Asdf.S01E02.720p'), (
            'Asdf.S01E02.720p should have been accepted'
        )

    def test_diff_qualities_not_allowed(self, execute_task):
        """Exists_series plugin: existsting but w. diff quality."""
        task = execute_task('test_diff_qualities_not_allowed')
        assert task.find_entry('rejected', title='Asdf.S01E02.720p'), (
            'Asdf.S01E02.720p should have been rejected'
        )

    def test_diff_qualities_downgrade(self, execute_task):
        """Test worse qualities than exist are rejected."""
        task = execute_task('test_diff_qualities_downgrade')
        assert task.find_entry('rejected', title='Asdf.S01E02.sdtv'), (
            'Asdf.S01E02.sdtv should have been rejected'
        )

    def test_diff_qualities_upgrade(self, execute_task):
        """Test better qualities than exist are accepted."""
        task = execute_task('test_diff_qualities_upgrade')
        assert task.find_entry('accepted', title='Asdf.S01E02.webdl'), (
            'Asdf.S01E02.webdl should have been rejected'
        )

    def test_propers(self, execute_task):
        """Exists_series plugin: new proper & proper already exists."""
        task = execute_task('test_propers')
        assert task.find_entry('accepted', title='Mock.S01E01.Proper'), 'new proper not accepted'
        assert task.find_entry('rejected', title='Test.S01E01'), (
            'pre-existin proper should have caused reject'
        )

    def test_invalid(self, execute_task):
        """Exists_series plugin: no episode numbering on the disk."""
        # shouldn't raise anything
        execute_task('test_invalid')

    def test_with_metainfo_series(self, execute_task):
        """Tests that exists_series works with series data from metainfo_series."""
        task = execute_task('test_with_metainfo_series')
        assert task.find_entry('rejected', title='Foo.Bar.S01E02.XViD'), (
            'Foo.Bar.S01E02.XViD should have been rejected(exists)'
        )
        assert not task.find_entry('rejected', title='Foo.Bar.S01E03.XViD'), (
            'Foo.Bar.S01E03.XViD should not have been rejected'
        )

    def test_jinja_path(self, manager, execute_task):
        manager.config['tasks']['test_jinja_path']['exists_series'] += '/{{series_name}}'
        task = execute_task('test_jinja_path')
        assert task.find_entry('rejected', title='jinja s01e01'), (
            'jinja s01e01 should have been rejected (exists)'
        )
        assert task.find_entry('rejected', title='jinja2 s01e01'), (
            'jinja2 s01e01 should have been rejected (exists)'
        )
        assert task.find_entry('accepted', title='jinja s01e02'), (
            'jinja s01e02 should have been accepted'
        )
