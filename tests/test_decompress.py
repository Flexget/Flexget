from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest
import os.path

try:
    import rarfile
except ImportError:
    rarfile = None


@pytest.mark.usefixtures('tmpdir')
class TestExtract(object):
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
                    
        """

    # Files
    rar_name = 'test_rar.rar'
    zip_name = 'test_zip.zip'
    out_file = 'hooray.txt'

    # Directories
    source_dir = 'archives'
    out_dir = 'directory'

    # Paths
    rar_path = os.path.join(source_dir, rar_name)
    zip_path = os.path.join(source_dir, zip_name)

    @pytest.mark.skipif(rarfile is None, reason='rarfile module required')
    @pytest.mark.filecopy(rar_path, '__tmp__')
    def test_rar(self, execute_task, tmpdir):
        """Test basic RAR extraction"""
        execute_task('test_rar')

        assert tmpdir.join(self.out_file).exists(), 'Output file does not exist at the correct path.'
        assert tmpdir.join(self.rar_name).exists(), 'RAR archive should still exist.'

    @pytest.mark.skipif(rarfile is None, reason='rarfile module required')
    @pytest.mark.filecopy(rar_path, '__tmp__')
    def test_delete_rar(self, execute_task, tmpdir):
        """Test RAR deletion after extraction"""
        execute_task('test_delete_rar')
        assert not tmpdir.join(self.rar_name).exists(), 'RAR archive was not deleted.'

    @pytest.mark.filecopy(zip_path, '__tmp__')
    def test_zip(self, execute_task, tmpdir):
        """Test basic Zip extraction"""
        execute_task('test_zip')
        assert tmpdir.join(self.out_file).exists(), 'Output file does not exist at the correct path.'
        assert tmpdir.join(self.zip_name).exists(), 'Zip archive should still exist.'

    @pytest.mark.filecopy(zip_path, '__tmp__')
    def test_keep_dirs(self, execute_task, tmpdir):
        """Test directory creation"""
        execute_task('test_keep_dirs')
        assert tmpdir.join(self.out_dir, self.out_file).exists(), 'Output file does not exist at the correct path.'

    @pytest.mark.filecopy(zip_path, '__tmp__')
    def test_delete_zip(self, execute_task, tmpdir):
        """Test Zip deletion after extraction"""
        execute_task('test_delete_zip')
        assert not tmpdir.join(self.zip_name).exists(), 'Zip archive was not deleted.'
