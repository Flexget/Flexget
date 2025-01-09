import platform

import pytest


class TestTorrentMatch:
    config = """
        tasks:
          test_multi_torrent_empty_name:
            mock:
              - {title: 'torrent1', file: 'torrent_match_test_torrents/torrent1_empty_name.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'torrent1', location: 'torrent_match_test_dir/torrent1'}
          test_single_torrent:
            mock:
              - {title: 'torrent1', file: 'torrent_match_test_torrents/torrent1.mkv.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'torrent1.mkv', location: 'torrent_match_test_dir/torrent1.mkv'}
          test_single_torrent_in_other_dir:
            mock:
              - {title: 'torrent1', file: 'torrent_match_test_torrents/torrent1.mkv.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'torrent1.mkv', location: 'torrent_match_test_dir/torrent1/torrent1.mkv'}
          test_single_torrent_wrong_size:
            mock:
              - {title: 'torrent1', file: 'torrent_match_test_torrents/torrent1.mkv.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'torrent1.mkv', location: 'torrent_match_test_dir/torrent1_wrong_size/torrent1.mkv'}
          test_multi_torrent_with_diff_not_allowed:
            mock:
              - {title: 'multi_file_with_diff', file: 'torrent_match_test_torrents/multi_file_with_diff.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'multi_file_with_diff', location: 'torrent_match_test_dir'}
          test_multi_torrent_with_diff_allowed:
            mock:
              - {title: 'multi_file_with_diff', file: 'torrent_match_test_torrents/multi_file_with_diff.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'multi_file_with_diff', location: 'torrent_match_test_dir'}
              max_size_difference: 5%
          test_multi_torrent_is_root_dir:
            mock:
              - {title: 'multi_file_with_diff', file: 'torrent_match_test_torrents/multi_file_with_diff.torrent'}
            accept_all: yes
            torrent_match:
              what:
                - mock:
                    - {title: 'multi_file_with_diff', location: 'torrent_match_test_dir/multi_file_with_diff'}
              max_size_difference: 5%

          test_with_filesystem:
            filesystem: 'torrent_match_test_torrents/'
            accept_all: yes
            torrent_match:
              what:
                - filesystem: 'torrent_match_test_dir/'
              max_size_difference: 5%

    """

    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='Due to the different file size calculation methods for torrents'
        ' created on Windows and Linux, allowing this test to pass on'
        'Windows will inevitably cause it to fail on Linux.',
    )
    def test_multi_torrent_empty_name(self, execute_task):
        task = execute_task('test_multi_torrent_empty_name')

        assert len(task.accepted) == 1, 'Should have accepted torrent1.mkv'
        assert task.accepted[0]['path'] == 'torrent_match_test_dir/torrent1'

    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='Due to the different file size calculation methods for torrents'
        ' created on Windows and Linux, allowing this test to pass on'
        'Windows will inevitably cause it to fail on Linux.',
    )
    def test_single_torrent(self, execute_task):
        task = execute_task('test_single_torrent')

        assert len(task.accepted) == 1, 'Should have accepted torrent1.mkv'
        assert task.accepted[0]['path'] == 'torrent_match_test_dir'

    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='Due to the different file size calculation methods for torrents'
        ' created on Windows and Linux, allowing this test to pass on'
        'Windows will inevitably cause it to fail on Linux.',
    )
    def test_single_torrent_in_other_dir(self, execute_task):
        task = execute_task('test_single_torrent_in_other_dir')

        assert len(task.accepted) == 1, 'Should have accepted torrent1.mkv'
        assert task.accepted[0]['path'] == 'torrent_match_test_dir/torrent1'

    def test_single_torrent_wrong_size(self, execute_task):
        task = execute_task('test_single_torrent_wrong_size')

        assert len(task.rejected) == 1, (
            'Should have rejected torrent1.mkv because its size does not match'
        )

    def test_multi_torrent_with_diff_not_allowed(self, execute_task):
        task = execute_task('test_multi_torrent_with_diff_not_allowed')

        assert len(task.rejected) == 1, (
            'Should have rejected multi_file_with_diff because its size does not match'
        )

    def test_multi_torrent_with_diff_allowed(self, execute_task):
        task = execute_task('test_multi_torrent_with_diff_allowed')

        assert len(task.accepted) == 1, (
            'Should have accepted multi_file_with_diff because its size is within threshold'
        )
        assert task.accepted[0]['path'] == 'torrent_match_test_dir'

    def test_multi_torrent_is_root_dir(self, execute_task):
        task = execute_task('test_multi_torrent_is_root_dir')

        assert len(task.accepted) == 1, (
            'Should have accepted multi_file_with_diff because its size is within threshold'
        )
        assert task.accepted[0]['path'] == 'torrent_match_test_dir'

    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='Due to the different file size calculation methods for torrents'
        ' created on Windows and Linux, allowing this test to pass on'
        'Windows will inevitably cause it to fail on Linux.',
    )
    def test_with_filesystem(self, execute_task):
        task = execute_task('test_with_filesystem')
        assert len(task.all_entries) == 4, (
            'There should be three torrent files, thus three entries'
        )
        assert len(task.accepted) == 4, (
            'Should have accepted multi_file_with_diff, torrent1.mkv, torrent2 and '
            'torrent1 because their sizes are within the allowed threshold'
        )
