from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import os

import mock
import pytest

from flexget.config_schema import parse_size


def mock_os_disk_stats(folder):
    used, total = os.path.basename(folder).split(',')

    used_bytes = parse_size(used)
    total_bytes = parse_size(total)
    free_bytes = total_bytes - used_bytes

    return free_bytes, total_bytes


@mock.patch('flexget.plugins.modify.path_by_space.os_disk_stats', side_effect=mock_os_disk_stats)
class TestPathSelect(object):
    config = """
        tasks:
          test_most_free:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 0G
              select: most_free
              paths:
                - /data/1.5G,100G
                - /data/50G,100G
                - /data/1G,100G
          test_most_free_within:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 1G
              select: most_free
              paths:
                - /data/49.5G,100G
                - /data/60G,100G
                - /data/50G,100G
                - /data/50.5G,100G
                - /data/80G,100G
          test_most_used:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 1G
              select: most_used
              paths:
                - /data/90G,100G
                - /data/80G,100G
                - /data/90.5G,100G
                - /data/88G,100G
          test_most_free_percent:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 2%
              select: most_free_percent
              paths:
                - /data/50G,100G
                - /data/40G,50G
                - /data/65G,80G
                - /data/50.5G,100G
          test_most_free_percent_within:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 2%
              select: most_free_percent
              paths:
                - /data/50G,100G
                - /data/50.5G,100G
                - /data/52G,100G
                - /data/57G,100G
                - /data/80G,100G
          test_most_used_percent:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 2%
              select: most_used_percent
              paths:
                - /data/99G,100G
                - /data/49G,50G
                - /data/40.5G,50G
                - /data/90.5G,100G
    """

    @pytest.fixture()
    def no_path_validation(self, monkeypatch):
        from flexget.config_schema import format_checker
        monkeypatch.delitem(format_checker.checkers, 'path')

    def test_most_free(self, disk_static_fun, no_path_validation, execute_task):
        task = execute_task('test_most_free')
        assert task.entries[0].get('path') == "/data/1G,100G"

    def test_most_free_within(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 3):
            task = execute_task('test_most_free_within')
            assert task.entries[0].get('path') in [
                "/data/49.5G,100G",
                "/data/50.5G,100G",
                "/data/50G,100G",
            ], "path %s not in list" % task.entries[0].get('path')

    def test_most_free_percent(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_free_percent')
            assert task.entries[0].get('path') in [
                '/data/50.5G,100G',
                '/data/50G,100G',
            ], "path %s not in list" % task.entries[0].get('path')

    def test_most_free_percent_within(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_free_percent_within')
            assert task.entries[0].get('path') in [
                '/data/50G,100G',
                '/data/50.5G,100G',
                '/data/52G,100G',
            ], "path %s not in list" % task.entries[0].get('path')

    def test_most_used_percent(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_used_percent')
            assert task.entries[0].get('path') in [
                '/data/99G,100G',
                '/data/49G,50G',
            ], "path %s not in list" % task.entries[0].get('path')

    def test_most_used(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_used')
            assert task.entries[0].get('path') in [
                '/data/90G,100G',
                '/data/90.5G,100G',
            ], "path %s not in list" % task.entries[0].get('path')
