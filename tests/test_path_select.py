from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
import os
import mock
from flexget.config_schema import parse_size


def mock_os_disk_stats(folder):

    used, total = os.path.basename(folder).split(',')

    used_bytes = parse_size(used)
    total_bytes = parse_size(total)
    free_bytes = total_bytes - used_bytes

    return free_bytes, total_bytes


class TestPathSelect(FlexGetBase):

    __yaml__ = """
        tasks:
          test_most_free:
            mock:
              - {title: 'Existence.2012'}
            path_select:
              to_field: path
              threshold: 0
              select: most_free
              paths:
                - /data/1.5G,100G
                - /data/50G,100G
                - /data/1G,100G
          test_most_free_threshold:
            mock:
              - {title: 'Existence.2012'}
            path_select:
              to_field: path
              threshold: 1G
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
            path_select:
              to_field: path
              threshold: 1G
              select: most_used
              paths:
                - /data/90G,100G
                - /data/80G,100G
                - /data/90.5G,100G
                - /data/88G,100G
          test_most_free_percent:
            mock:
              - {title: 'Existence.2012'}
            path_select:
              to_field: path
              threshold: 2%
              select: most_free_percent
              paths:
                - /data/50G,100G
                - /data/40G,50G
                - /data/65G,80G
                - /data/50.5G,100G
          test_most_used_percent:
            mock:
              - {title: 'Existence.2012'}
            path_select:
              to_field: path
              threshold: 2%
              select: most_used_percent
              paths:
                - /data/99G,100G
                - /data/49G,50G
                - /data/40.5G,50G
                - /data/90.5G,100G
          test_has_free:
            mock:
              - {title: 'Existence.2012'}
            path_select:
              to_field: path
              threshold: 50G
              select: has_free
              paths:
                - /data/65G,100G
                - /data/50.2G,100G
                - /data/45G,100G
                - /data/20G,100G
                - /data/30G,100G
                - /data/90G,100G
    """

    @mock.patch('flexget.plugins.modify.path_select.os_disk_stats', side_effect=mock_os_disk_stats)
    def test_most_free(self, disk_static_func):
        self.execute_task('test_most_free')
        assert self.task.entries[0].get('path') == "/data/1G,100G"

    @mock.patch('flexget.plugins.modify.path_select.os_disk_stats', side_effect=mock_os_disk_stats)
    def test_most_free_threshold(self, disk_static_func):
        for i in range(0, 3):
            self.execute_task('test_most_free_threshold')
            assert self.task.entries[0].get('path') in [
                "/data/49.5G,100G",
                "/data/50.5G,100G",
                "/data/50G,100G",
            ], "path %s not in list" % self.task.entries[0].get('path')

    @mock.patch('flexget.plugins.modify.path_select.os_disk_stats', side_effect=mock_os_disk_stats)
    def test_most_used(self, disk_static_func):
        for i in range(0, 2):
            self.execute_task('test_most_used')
            assert self.task.entries[0].get('path') in [
                '/data/90G,100G',
                '/data/90.5G,100G',
            ], "path %s not in list" % self.task.entries[0].get('path')

    @mock.patch('flexget.plugins.modify.path_select.os_disk_stats', side_effect=mock_os_disk_stats)
    def test_most_free_percent(self, disk_static_func):
        for i in range(0, 2):
            self.execute_task('test_most_free_percent')
            assert self.task.entries[0].get('path') in [
                '/data/50.5G,100G',
                '/data/50G,100G',
            ], "path %s not in list" % self.task.entries[0].get('path')

    @mock.patch('flexget.plugins.modify.path_select.os_disk_stats', side_effect=mock_os_disk_stats)
    def test_most_used_percent(self, disk_static_func):
        for i in range(0, 2):
            self.execute_task('test_most_used_percent')
            assert self.task.entries[0].get('path') in [
                '/data/99G,100G',
                '/data/49G,50G',
            ], "path %s not in list" % self.task.entries[0].get('path')

    @mock.patch('flexget.plugins.modify.path_select.os_disk_stats', side_effect=mock_os_disk_stats)
    def test_has_free(self, disk_static_func):
        for i in range(0, 3):
            self.execute_task('test_has_free')
            assert self.task.entries[0].get('path') in [
                '/data/45G,100G',
                '/data/20G,100G',
                '/data/30G,100G',
            ], "path %s not in list" % self.task.entries[0].get('path')
