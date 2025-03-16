import stat
from typing import TYPE_CHECKING

import pytest
from jinja2 import Template

if TYPE_CHECKING:
    from pathlib import Path

dirname = 'symlink_test_dir'
subdirs = ['hardlink', 'softlink']


def is_hard_link(file1: 'Path', file2: 'Path') -> bool:
    s1 = file1.stat()
    s2 = file2.stat()
    return (s1[stat.ST_INO], s1[stat.ST_DEV]) == (s2[stat.ST_INO], s2[stat.ST_DEV])


class TestSymlink:
    _config = """
        templates:
          global:
            accept_all: yes
            disable: builtins
        tasks:
          test_hardlink:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
            symlink:
              to: '{{tmpdir_1}}/hardlink'
              link_type: 'hard'
          test_hardlink_rename:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
            symlink:
              to: '{{tmpdir_1}}/hardlink'
              rename: 'rename.mkv'
              link_type: 'hard'
          test_hardlink_dir:
            mock:
              - {title: 'test2', location: '{{tmpdir_1}}/test2'}
            symlink:
              to: '{{tmpdir_1}}/hardlink'
              link_type: 'hard'
          test_hardlink_fail:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
            symlink:
              to: '{{tmpdir_1}}/hardlink'
              link_type: 'hard'
          test_softlink:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
              - {title: 'test1', location: '{{tmpdir_1}}/test1'}
            symlink:
              to: '{{tmpdir_1}}/softlink'
              link_type: 'soft'
          test_softlink_rename:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
            symlink:
              to: '{{tmpdir_1}}/softlink'
              rename: 'rename.mkv'
              link_type: 'soft'
          test_softlink_fail:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
              - {title: 'test1', location: '{{tmpdir_1}}/test1'}
            symlink:
              to: '{{tmpdir_1}}/softlink'
              link_type: 'soft'
    """

    @pytest.fixture
    def config(self, tmp_path):
        test_dir = tmp_path / dirname
        (test_dir / 'hardlink').mkdir(parents=True)
        (test_dir / 'softlink').mkdir(parents=True)

        return Template(self._config).render({'tmpdir_1': test_dir})

    def test_hardlink(self, execute_task, tmp_path):
        (tmp_path / dirname / 'test1.mkv').write_text('')
        execute_task('test_hardlink')
        hardlink = tmp_path / dirname / 'hardlink' / 'test1.mkv'

        assert hardlink.exists(), f'{hardlink} should exist'
        assert is_hard_link(tmp_path / dirname / 'test1.mkv', hardlink)

    def test_hardlink_rename(self, execute_task, tmp_path):
        (tmp_path / dirname / 'test1.mkv').write_text('')
        execute_task('test_hardlink_rename')
        hardlink = tmp_path / dirname / 'hardlink' / 'rename.mkv'

        assert hardlink.exists(), f'{hardlink} should exist'
        assert is_hard_link(tmp_path / dirname / 'test1.mkv', hardlink)

    def test_hardlink_dir(self, execute_task, tmp_path):
        tmp = tmp_path / dirname / 'test2'
        tmp.mkdir()
        test2 = tmp / 'test2.mkv'
        test2.write_text('')
        execute_task('test_hardlink_dir')
        hardlink_dir = tmp_path / dirname / 'hardlink' / 'test2'

        assert hardlink_dir.exists(), f'{hardlink_dir} should exist'
        assert is_hard_link(test2, hardlink_dir / 'test2.mkv')

    def test_hardlink_fail(self, execute_task, tmp_path):
        (tmp_path / dirname / 'test1.mkv').write_text('')
        hardlink = tmp_path / dirname / 'hardlink' / 'test1.mkv'
        hardlink.write_text('')
        task = execute_task('test_hardlink')

        assert len(task.failed) == 1, 'should have failed test1.mkv'

    def test_softlink(self, execute_task, tmp_path):
        (tmp_path / dirname / 'test1.mkv').write_text('')
        (tmp_path / dirname / 'test1').mkdir()
        execute_task('test_softlink')

        softlink = tmp_path / dirname / 'softlink'
        f = softlink / 'test1.mkv'
        d = softlink / 'test1'
        assert f.exists(), f'{f} should exist'
        assert d.exists(), f'{d} should exist'
        assert f.is_symlink(), f'{f} should be a softlink'
        assert d.is_symlink(), f'{d} should be a softlink'

    def test_softlink_rename(self, execute_task, tmp_path):
        (tmp_path / dirname / 'test1.mkv').write_text('')
        execute_task('test_softlink_rename')

        softlink = tmp_path / dirname / 'softlink'
        f = softlink / 'rename.mkv'
        assert f.exists(), f'{f} should exist'
        assert f.is_symlink(), f'{f} should be a softlink'

    def test_softlink_fail(self, execute_task, tmp_path):
        (tmp_path / dirname / 'test1.mkv').write_text('')
        (tmp_path / dirname / 'test1').mkdir()

        (tmp_path / dirname / 'softlink' / 'test1.mkv').write_text('')
        (tmp_path / dirname / 'softlink' / 'test1').mkdir()
        task = execute_task('test_softlink_fail')

        assert len(task.failed) == 2, 'Should have failed both entries since they already exist'
