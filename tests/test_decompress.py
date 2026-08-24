from pathlib import Path

import pytest

from flexget.components.archives import utils as archiveutil
from flexget.components.archives.decompress import get_destination_path


@pytest.mark.require_optional_deps
class TestExtract:
    config = """
        templates:
            global:
                accept_all: yes
            rar_file:
                mock:
                    - {title: 'test', location: '__tmp__/test_rar.rar'}
            zip_file:
                mock:
                    - {title: 'test', location: '__tmp__/test_zip.zip'}
            empty_path:
                mock:
                    - {title: 'test', location: ''}
            file_not_exists:
                mock:
                    - {title: 'test', location: '__tmp__/nothing_here.zip'}
            no_path:
                mock:
                    - {title: 'test'}
        tasks:
            test_rar:
                template: rar_file
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
            test_zip:
                template: zip_file
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
            test_keep_dirs:
                template: zip_file
                decompress:
                    to: '__tmp__'
                    keep_dirs: yes
            test_delete_rar:
                template: rar_file
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
                    delete_archive: yes
            test_delete_zip:
                template: zip_file
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
                    delete_archive: yes
            test_empty_path:
                template: empty_path
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
            test_no_path:
                template: no_path
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
                    delete_archive: yes
            test_file_not_exists:
                template: file_not_exists
                decompress:
                    to: '__tmp__'
                    keep_dirs: no
                    delete_archive: yes
        """

    # Files
    rar_name = 'test_rar.rar'
    zip_name = 'test_zip.zip'
    out_file = 'hooray.txt'

    # Directories
    source_dir = Path('archives')
    out_dir = Path('directory')

    # Paths
    rar_path = source_dir / rar_name
    zip_path = source_dir / zip_name

    # Error messages
    error_not_local = 'Entry does not appear to represent a local file.'
    error_not_exists = 'File no longer exists:'

    @pytest.mark.filecopy(rar_path, '__tmp__')
    def test_rar(self, execute_task, tmp_path):
        """Test basic RAR extraction."""
        execute_task('test_rar')

        assert (tmp_path / self.out_file).exists(), (
            'Output file does not exist at the correct path.'
        )
        assert (tmp_path / self.rar_name).exists(), 'RAR archive should still exist.'

    @pytest.mark.filecopy(rar_path, '__tmp__')
    def test_delete_rar(self, execute_task, tmp_path):
        """Test RAR deletion after extraction."""
        execute_task('test_delete_rar')
        assert not (tmp_path / self.rar_name).exists(), 'RAR archive was not deleted.'

    @pytest.mark.filecopy(zip_path, '__tmp__')
    def test_zip(self, execute_task, tmp_path):
        """Test basic Zip extraction."""
        execute_task('test_zip')
        assert (tmp_path / self.out_file).exists(), (
            'Output file does not exist at the correct path.'
        )
        assert (tmp_path / self.zip_name).exists(), 'Zip archive should still exist.'

    @pytest.mark.filecopy(zip_path, '__tmp__')
    def test_keep_dirs(self, execute_task, tmp_path):
        """Test directory creation."""
        execute_task('test_keep_dirs')
        assert (tmp_path / self.out_dir / self.out_file).exists(), (
            'Output file does not exist at the correct path.'
        )

    @pytest.mark.filecopy(zip_path, '__tmp__')
    def test_delete_zip(self, execute_task, tmp_path):
        """Test Zip deletion after extraction."""
        execute_task('test_delete_zip')
        assert not (tmp_path / self.zip_name).exists(), 'Zip archive was not deleted.'

    def test_empty_path(self, execute_task, caplog):
        """Test when an empty location is provided."""
        execute_task('test_empty_path')
        assert self.error_not_local in caplog.text, (
            'Plugin logs an error when entry has an empty path.'
        )

    def test_no_path(self, execute_task, caplog):
        """Test when no location is provided."""
        execute_task('test_no_path')
        assert self.error_not_local in caplog.text, 'Plugin logs an error when entry has no path.'

    def test_not_a_file(self, execute_task, caplog):
        """Test when a non-existent path is provided."""
        execute_task('test_file_not_exists')
        assert self.error_not_exists in caplog.text, (
            'Plugin logs an error when file does not exist.'
        )


class FakeInfo:
    def __init__(self, path):
        self.path = path


class TestGetDestinationPath:
    """Regression tests for the Zip Slip / path traversal fix."""

    @pytest.mark.parametrize(
        'evil_path',
        [
            '../../../etc/passwd',
            '../outside.txt',
            '/etc/passwd',
        ],
    )
    def test_rejects_paths_escaping_destination(self, tmp_path, evil_path):
        to = tmp_path / 'safe_extract'
        to.mkdir()
        with pytest.raises(archiveutil.PathTraversalError):
            get_destination_path(FakeInfo(evil_path), to, keep_dirs=True)

    def test_allows_normal_paths(self, tmp_path):
        to = tmp_path / 'safe_extract'
        to.mkdir()
        destination = get_destination_path(FakeInfo('subdir/file.txt'), to, keep_dirs=True)
        assert destination == (to / 'subdir' / 'file.txt').resolve()
