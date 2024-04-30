import os
from unittest import mock

import pytest

from flexget.config_schema import parse_size


def mock_os_disk_stats(folder):
    used, total = os.path.basename(folder).split(',')

    used_bytes = parse_size(used)
    total_bytes = parse_size(total)
    free_bytes = total_bytes - used_bytes

    return free_bytes, total_bytes


@mock.patch('flexget.plugins.modify.path_by_space.os_disk_stats', side_effect=mock_os_disk_stats)
class TestPathSelect:
    config = """
        tasks:
          test_most_free:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 0GB
              select: most_free
              paths:
                - /data/1.5GB,100GB
                - /data/50GB,100GB
                - /data/1GB,100GB
          test_most_free_within:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 1GB
              select: most_free
              paths:
                - /data/49.5GB,100GB
                - /data/60GB,100GB
                - /data/50GB,100GB
                - /data/50.5GB,100GB
                - /data/80GB,100GB
          test_most_used:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 1GB
              select: most_used
              paths:
                - /data/90GB,100GB
                - /data/80GB,100GB
                - /data/90.5GB,100GB
                - /data/88GB,100GB
          test_most_free_percent:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 2%
              select: most_free_percent
              paths:
                - /data/50GB,100GB
                - /data/40GB,50GB
                - /data/65GB,80GB
                - /data/50.5GB,100GB
          test_most_free_percent_within:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 2%
              select: most_free_percent
              paths:
                - /data/50GB,100GB
                - /data/50.5GB,100GB
                - /data/52GB,100GB
                - /data/57GB,100GB
                - /data/80GB,100GB
          test_most_used_percent:
            mock:
              - {title: 'Existence.2012'}
            path_by_space:
              to_field: path
              within: 2%
              select: most_used_percent
              paths:
                - /data/99GB,100GB
                - /data/49GB,50GB
                - /data/40.5GB,50GB
                - /data/90.5GB,100GB
    """

    @pytest.fixture()
    def no_path_validation(self, monkeypatch):
        from flexget.config_schema import format_checker

        monkeypatch.delitem(format_checker.checkers, 'path')

    def test_most_free(self, disk_static_fun, no_path_validation, execute_task):
        task = execute_task('test_most_free')
        assert task.entries[0].get('path') == "/data/1GB,100GB"

    def test_most_free_within(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 3):
            task = execute_task('test_most_free_within')
            assert task.entries[0].get('path') in [
                "/data/49.5GB,100GB",
                "/data/50.5GB,100GB",
                "/data/50GB,100GB",
            ], "path {} not in list".format(task.entries[0].get('path'))

    def test_most_free_percent(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_free_percent')
            assert task.entries[0].get('path') in [
                '/data/50.5GB,100GB',
                '/data/50GB,100GB',
            ], "path {} not in list".format(task.entries[0].get('path'))

    def test_most_free_percent_within(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_free_percent_within')
            assert task.entries[0].get('path') in [
                '/data/50GB,100GB',
                '/data/50.5GB,100GB',
                '/data/52GB,100GB',
            ], "path {} not in list".format(task.entries[0].get('path'))

    def test_most_used_percent(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_used_percent')
            assert task.entries[0].get('path') in [
                '/data/99GB,100GB',
                '/data/49GB,50GB',
            ], "path {} not in list".format(task.entries[0].get('path'))

    def test_most_used(self, disk_static_func, no_path_validation, execute_task):
        for _ in range(0, 2):
            task = execute_task('test_most_used')
            assert task.entries[0].get('path') in [
                '/data/90GB,100GB',
                '/data/90.5GB,100GB',
            ], "path {} not in list".format(task.entries[0].get('path'))
