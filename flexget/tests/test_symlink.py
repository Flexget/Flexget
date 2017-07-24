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
              - {title: 'test1.mkv', location: 'symlink_test_dir/test1.mkv'}
            symlink:
              to: 'symlink_test_dir/hardlink'
              link_type: 'hard'
    """

    def setup_method(self, test_method):
        # Create required dirs for tests
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        for subdir in subdirs:
            if not os.path.exists(os.path.join(dirname, subdir)):
                os.mkdir(os.path.join(dirname, subdir))

    def teardown_method(self, test_method):
        # teardown
        shutil.rmtree(dirname)

    def test_sort_by(self, execute_task):
        os.utime('symlink_test_dir/test1.mkv', None)
        execute_task('test_hardlink')
        assert os.path.exists('symlink_test_dir/hardlink/test1.mkv'), 'symlink_test_dir/hardlink/test1.mkv should exist'
        assert is_hard_link('symlink_test_dir/hardlink/test1.mkv', 'symlink_test_dir/test1.mkv')

        try:
            os.remove('symlink_test_dir/test1.mkv')
        except OSError:
            pass
