from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import pytest

from flexget.task import Task, TaskAbort

if TYPE_CHECKING:
    from .test_sftp_server import TestSFTPFileSystem, TestSFTPServerController


@pytest.mark.require_optional_deps
@pytest.mark.xdist_group(name="sftp")
class TestSftpList:
    config = """
        templates:
          anchors:
            _base_sftp_list: &base_sftp_list
                host: 127.0.0.1
                port: 40022
                host_key:
                  key_type: 'ssh-rsa'
                  public_key: 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj'
                socket_timeout_sec: 2
                connection_tries: 1
            _sftp_basic_auth: &sftp_basic_auth
                username: test_user
                password: test_pass

        tasks:
          sftp_list_bad_login:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth

          sftp_list:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth

          sftp_list_dirs_absolute:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              dirs:
                - '/downloads'

          sftp_list_recursive_true:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              recursive: True

          sftp_list_files_only_false:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              files_only: False

          sftp_list_files_only_false_recursive_true:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              files_only: False
              recursive: True

          sftp_list_get_size_true_files_only_false_recursive_true:
            sftp_list:
              <<: *base_sftp_list
              <<: *sftp_basic_auth
              files_only: False
              get_size: True
              recursive: True

          sftp_list_private_key:
            sftp_list:
              <<: *base_sftp_list
              username: test_user
              private_key: 'test_sftp_user_key'
              private_key_pass: 'password'
    """

    @pytest.fixture
    def sftp_fs(self, sftp: TestSFTPServerController) -> TestSFTPFileSystem:
        return sftp.start()

    def test_sftp_list_bad_login(
        self, execute_task: Callable[..., Task], sftp: TestSFTPServerController
    ):
        sftp.start(username='foo', password='bar')

        with pytest.raises(TaskAbort) as ex:
            execute_task('sftp_list_bad_login')

        assert ex.value.reason == 'Failed to connect to 127.0.0.1'

    def test_sftp_list_files(self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem):
        sftp_fs.create_file('file.mkv')

        assert_entries(
            execute_task('sftp_list'),
            {
                'title': 'file.mkv',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/file.mkv',
            },
        )

    def test_sftp_list_files_recursive_false(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('dir/file.mkv')

        assert_no_entries(execute_task('sftp_list'))

    def test_sftp_list_files_recursive_true(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('dir/file.mkv')

        assert_entries(
            execute_task('sftp_list_recursive_true'),
            {
                'title': 'file.mkv',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir/file.mkv',
            },
        )

    def test_sftp_list_dirs(self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem):
        sftp_fs.create_dir('dir')

        assert_entries(
            execute_task('sftp_list_files_only_false'),
            {
                'title': 'dir',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir',
            },
        )

    def test_sftp_list_dirs_recursive_false(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_dir('dir/nested')

        assert_entries(
            execute_task('sftp_list_files_only_false'),
            {
                'title': 'dir',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir',
            },
        )

    def test_sftp_list_dirs_recursive_true(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_dir('dir/nested')

        assert_entries(
            execute_task('sftp_list_files_only_false_recursive_true'),
            {
                'title': 'dir',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir',
            },
            {
                'title': 'nested',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir/nested',
            },
        )

    def test_sftp_list_file_size(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv', 24)

        assert_entries(
            execute_task('sftp_list_get_size_true_files_only_false_recursive_true'),
            {
                'title': 'file.mkv',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/file.mkv',
                'content_size': 24,
            },
        )

    def test_sftp_list_dir_size(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('dir/file1.mkv', 40)
        sftp_fs.create_file('dir/file2.mkv', 60)

        assert_entries(
            execute_task('sftp_list_get_size_true_files_only_false_recursive_true'),
            {
                'title': 'dir',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir',
                'content_size': 100,
            },
            allow_unexpected_entires=True,
        )

    def test_sftp_list_symlink_file(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_symlink('file.mkv', sftp_fs.create_file('/target.mkv', 100))

        assert_entries(
            execute_task('sftp_list'),
            {
                'title': 'file.mkv',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/file.mkv',
            },
        )

    def test_sftp_list_symlink_dir(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_symlink('dir', sftp_fs.create_dir('/target_dir'))
        sftp_fs.create_file('/target_dir/file.mkv')

        assert_entries(
            execute_task('sftp_list_recursive_true'),
            {
                'title': 'file.mkv',
                'url': 'sftp://test_user:test_pass@127.0.0.1:40022/home/test_user/dir/file.mkv',
            },
        )

    def test_sftp_list_uses_private_key_auth(
        self, execute_task: Callable[..., Task], sftp: TestSFTPServerController
    ):
        sftp_fs: TestSFTPFileSystem = sftp.start(key_only=True)
        sftp_fs.create_file('file.mkv')

        execute_task('sftp_list_private_key')

    def test_sftp_list_private_key_set_on_entry(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv')

        assert_entries(
            execute_task('sftp_list_private_key'),
            {'title': 'file.mkv', 'private_key': 'test_sftp_user_key'},
        )

    def test_sftp_list_private_key_pass_set_on_entry(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv')

        assert_entries(
            execute_task('sftp_list_private_key'),
            {'title': 'file.mkv', 'private_key_pass': 'password'},
        )

    def test_sftp_list_host_key_set_on_entry(
        self, execute_task: Callable[..., Task], sftp_fs: TestSFTPFileSystem
    ):
        sftp_fs.create_file('file.mkv')

        assert_entries(
            execute_task('sftp_list'),
            {
                'title': 'file.mkv',
                'host_key': {
                    'key_type': 'ssh-rsa',
                    'public_key': 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC7Hn9BizDY6wI1oNYUBoVHAVioXzOJkZDPB+QsUHDBOqVIcdL/glfMtgIO1E5khoBYql8DSSI+EyrxaC+mfeJ7Ax5qZnimOFvZsJvwvO5h7LI4W1KkoJrYUfMLFfHkDy5EbPIuXeAQGdF/JzOXoIqMcCmKQDS56WRDnga91CGQeXAuzINiviZ63R55b8ynN2JFqKW5V6WZiYZBSmTia68s2ZefkFMiv7E6gmD4WYj6hitz8FGPUoyFAGIR+NVqZ5i9l/8CDuNcZ8E8G7AmNFQhChAeQdEOPO0f2vdH6aRb8Cn0EAy6zpBllxQO8EuLjiEfH01n4/VlGeQEiXlyCLqj',
                },
            },
        )


def assert_entries(
    task: Task,
    entry_matcher: dict[str, Any],
    *argv: dict[str, Any],
    allow_unexpected_entires: bool = False,
):
    """Assert that the entries generated for a given task match the list of dictionaries given as entry matches.

    Only the keys specified will be checked for.

    :param task: Task to assert the entries from.
    :param entry_matcher: Dict continain the expected entry values, must have at least a 'title'
                          set.
    :param allow_unexpected_entires: bool to assert if there are any additional entries generated
                                     that matchers arn't specified for.
    """
    expected = [m['title'] for m in [entry_matcher, *argv]]
    found = [m['title'] for m in task.all_entries]
    if not allow_unexpected_entires:
        unexpected: list[str] = [title for title in found if title not in expected]
        assert not unexpected, f'Found unexpected entries {unexpected}'

    not_found: list[str] = [title for title in expected if title not in found]
    assert not not_found, f'Entires not found {not_found} in {found}'

    for matcher in [entry_matcher, *argv]:
        entry = task.find_entry(title=matcher['title'])
        assert entry, f"Expected entry with title {matcher['title']}, but found none"
        for k, v in matcher.items():
            assert k in entry.store, f"Expected entry {matcher['title']} to have attribute {k}"
            assert entry[k] == v, (
                f"Expected entry {matcher['title']} to have value {v} for attribute {k}, but was {entry[k]}"
            )


def assert_no_entries(task: Task):
    """Assert that there are no entries generated for a given task.

    :param task: Task to assert no entires are generated for.
    """
    assert len(task.all_entries) == 0, (
        f"Expected no entries, but found {[m['title'] for m in task.all_entries]}"
    )
