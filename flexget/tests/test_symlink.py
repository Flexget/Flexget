from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

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


@pytest.mark.skipif(os.name != 'posix', reason='symlinks only work on posix')
class TestSymlink(object):
    _config = """
        templates:
          global:
            accept_all: yes
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
    """

    @pytest.fixture
    def config(self, tmpdir):
        test_dir = tmpdir.mkdir(dirname)
        test_dir.mkdir('hardlink')

        return Template(self._config).render({'tmpdir_1': test_dir.strpath})

    def test_hardlink(self, execute_task, tmpdir):
        tmpdir.join(dirname).join('test1.mkv').write('')
        execute_task('test_hardlink')
        hardlink = tmpdir.join(dirname).join('hardlink').join('test1.mkv')

        assert os.path.exists(hardlink.strpath), '%s should exist' % hardlink.strpath
        assert is_hard_link(tmpdir.join(dirname).join('test1.mkv').strpath, hardlink.strpath)

    def test_hardlink_dir(self, execute_task, tmpdir):
        tmp = tmpdir.join(dirname).mkdir('test2')
        test2 = tmp.join('test2.mkv').write('')
        execute_task('test_hardlink_dir')
        hardlink_dir = tmpdir.join(dirname).join('hardlink').join('test2')

        assert os.path.exists(hardlink_dir.strpath), '%s should exist' % hardlink_dir.strpath
        assert is_hard_link(test2.strpath, hardlink_dir.join('test2.mkv').strpath)
