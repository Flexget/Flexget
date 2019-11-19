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


@pytest.mark.skipif(os.name == 'nt', reason='symlinks do not work on windows')
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
          test_softlink_fail:
            mock:
              - {title: 'test1.mkv', location: '{{tmpdir_1}}/test1.mkv'}
              - {title: 'test1', location: '{{tmpdir_1}}/test1'}
            symlink:
              to: '{{tmpdir_1}}/softlink'
              link_type: 'soft'
    """

    @pytest.fixture
    def config(self, tmpdir):
        test_dir = tmpdir.mkdir(dirname)
        test_dir.mkdir('hardlink')
        test_dir.mkdir('softlink')

        return Template(self._config).render({'tmpdir_1': test_dir.strpath})

    def test_hardlink(self, execute_task, tmpdir):
        tmpdir.join(dirname).join('test1.mkv').write('')
        execute_task('test_hardlink')
        hardlink = tmpdir.join(dirname).join('hardlink').join('test1.mkv')

        assert os.path.exists(hardlink.strpath), '%s should exist' % hardlink.strpath
        assert is_hard_link(tmpdir.join(dirname).join('test1.mkv').strpath, hardlink.strpath)

    def test_hardlink_dir(self, execute_task, tmpdir):
        tmp = tmpdir.join(dirname).mkdir('test2')
        test2 = tmp.join('test2.mkv')
        test2.write('')
        execute_task('test_hardlink_dir')
        hardlink_dir = tmpdir.join(dirname).join('hardlink').join('test2')

        assert os.path.exists(hardlink_dir.strpath), '%s should exist' % hardlink_dir.strpath
        assert is_hard_link(test2.strpath, hardlink_dir.join('test2.mkv').strpath)

    def test_hardlink_fail(self, execute_task, tmpdir):
        tmpdir.join(dirname).join('test1.mkv').write('')
        hardlink = tmpdir.join(dirname).join('hardlink').join('test1.mkv')
        hardlink.write('')
        task = execute_task('test_hardlink')

        assert len(task.failed) == 1, 'should have failed test1.mkv'

    def test_softlink(self, execute_task, tmpdir):
        tmpdir.join(dirname).join('test1.mkv').write('')
        tmpdir.join(dirname).mkdir('test1')
        execute_task('test_softlink')

        softlink = tmpdir.join(dirname).join('softlink')
        f = softlink.join('test1.mkv')
        d = softlink.join('test1')
        assert os.path.exists(f.strpath), '%s should exist' % f.strpath
        assert os.path.exists(d.strpath), '%s should exist' % d.strpath
        assert os.path.islink(f.strpath), '%s should be a softlink' % f.strpath
        assert os.path.islink(d.strpath), '%s should be a softlink' % d.strpath

    def test_softlink_fail(self, execute_task, tmpdir):
        tmpdir.join(dirname).join('test1.mkv').write('')
        tmpdir.join(dirname).mkdir('test1')

        tmpdir.join(dirname).join('softlink').join('test1.mkv').write('')
        tmpdir.join(dirname).join('softlink').mkdir('test1')
        task = execute_task('test_softlink_fail')

        assert len(task.failed) == 2, 'Should have failed both entries since they already exist'
