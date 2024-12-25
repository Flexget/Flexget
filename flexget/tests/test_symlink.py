import os
import stat

import pytest
from jinja2 import Template

dirname = 'symlink_test_dir'
subdirs = ['hardlink', 'softlink']


def is_hard_link(file1, file2):
    s1 = os.stat(file1)
    s2 = os.stat(file2)
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
        test_dir = tmp_path.joinpath(dirname)
        test_dir.joinpath('hardlink').mkdir(parents=True)
        test_dir.joinpath('softlink').mkdir(parents=True)

        return Template(self._config).render({'tmpdir_1': test_dir.as_posix()})

    def test_hardlink(self, execute_task, tmp_path):
        tmp_path.joinpath(dirname).joinpath('test1.mkv').write_text('')
        execute_task('test_hardlink')
        hardlink = tmp_path.joinpath(dirname).joinpath('hardlink').joinpath('test1.mkv')

        assert os.path.exists(hardlink.as_posix()), f'{hardlink.as_posix()} should exist'
        assert is_hard_link(
            tmp_path.joinpath(dirname).joinpath('test1.mkv').as_posix(), hardlink.as_posix()
        )

    def test_hardlink_rename(self, execute_task, tmp_path):
        tmp_path.joinpath(dirname).joinpath('test1.mkv').write_text('')
        execute_task('test_hardlink_rename')
        hardlink = tmp_path.joinpath(dirname).joinpath('hardlink').joinpath('rename.mkv')

        assert os.path.exists(hardlink.as_posix()), f'{hardlink.as_posix()} should exist'
        assert is_hard_link(
            tmp_path.joinpath(dirname).joinpath('test1.mkv').as_posix(), hardlink.as_posix()
        )

    def test_hardlink_dir(self, execute_task, tmp_path):
        tmp = tmp_path.joinpath(dirname).joinpath('test2')
        tmp.mkdir()
        test2 = tmp.joinpath('test2.mkv')
        test2.write_text('')
        execute_task('test_hardlink_dir')
        hardlink_dir = tmp_path.joinpath(dirname).joinpath('hardlink').joinpath('test2')

        assert os.path.exists(hardlink_dir.as_posix()), f'{hardlink_dir.as_posix()} should exist'
        assert is_hard_link(test2.as_posix(), hardlink_dir.joinpath('test2.mkv').as_posix())

    def test_hardlink_fail(self, execute_task, tmp_path):
        tmp_path.joinpath(dirname).joinpath('test1.mkv').write_text('')
        hardlink = tmp_path.joinpath(dirname).joinpath('hardlink').joinpath('test1.mkv')
        hardlink.write_text('')
        task = execute_task('test_hardlink')

        assert len(task.failed) == 1, 'should have failed test1.mkv'

    def test_softlink(self, execute_task, tmp_path):
        tmp_path.joinpath(dirname).joinpath('test1.mkv').write_text('')
        tmp_path.joinpath(dirname).joinpath('test1').mkdir()
        execute_task('test_softlink')

        softlink = tmp_path.joinpath(dirname).joinpath('softlink')
        f = softlink.joinpath('test1.mkv')
        d = softlink.joinpath('test1')
        assert os.path.exists(f.as_posix()), f'{f.as_posix()} should exist'
        assert os.path.exists(d.as_posix()), f'{d.as_posix()} should exist'
        assert os.path.islink(f.as_posix()), f'{f.as_posix()} should be a softlink'
        assert os.path.islink(d.as_posix()), f'{d.as_posix()} should be a softlink'

    def test_softlink_rename(self, execute_task, tmp_path):
        tmp_path.joinpath(dirname).joinpath('test1.mkv').write_text('')
        execute_task('test_softlink_rename')

        softlink = tmp_path.joinpath(dirname).joinpath('softlink')
        f = softlink.joinpath('rename.mkv')
        assert os.path.exists(f.as_posix()), f'{f.as_posix()} should exist'
        assert os.path.islink(f.as_posix()), f'{f.as_posix()} should be a softlink'

    def test_softlink_fail(self, execute_task, tmp_path):
        tmp_path.joinpath(dirname).joinpath('test1.mkv').write_text('')
        tmp_path.joinpath(dirname).joinpath('test1').mkdir()

        tmp_path.joinpath(dirname).joinpath('softlink').joinpath('test1.mkv').write_text('')
        tmp_path.joinpath(dirname).joinpath('softlink').joinpath('test1').mkdir()
        task = execute_task('test_softlink_fail')

        assert len(task.failed) == 2, 'Should have failed both entries since they already exist'
