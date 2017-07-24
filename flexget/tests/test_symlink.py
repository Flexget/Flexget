from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import shutil
import stat

import pytest

dirname = 'symlink_test_dir'
subdirs = ['hardlink', 'softlink']


def is_hard_link(file1, file2):
    s1 = os.stat(file1)
    s2 = os.stat(file2)
    return (s1[stat.ST_INO], s1[stat.ST_DEV]) == (s2[stat.ST_INO], s2[stat.ST_DEV])


@pytest.mark.skipif(os.name != 'posix', reason='symlinks only work on posix')
class TestSymlink(object):
    config = """
        templates:
          global:
            accept_all: yes
        tasks:
          test_hardlink:
            mock:
              - {title: 'test1.mkv', location: '__tmp__/symlink_test_dir/test1.mkv'}
            symlink:
              to: '__tmp__/symlink_test_dir/hardlink'
              link_type: 'hard'
    """

    @pytest.fixture
    def create_tmp_dirs(self, tmpdir):
        # Create required dirs for tests
        tmp = tmpdir.mkdir(dirname)

        for subdir in subdirs:
            tmp.mkdir(subdir)

    def test_hardlink(self, execute_task, tmpdir):
        tmpdir.join(dirname).join('test1.mkv').write('')
        execute_task('test_hardlink')
        org_file = tmpdir.join(dirname).join('test1.mkv')
        assert os.path.exists(org_file), 'test1.mkv should exist'
        assert is_hard_link(org_file, tmpdir.join(dirname).join('hardlink').join('test1.mkv'))
