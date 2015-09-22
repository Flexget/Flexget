from __future__ import unicode_literals, division, absolute_import
import os
import shutil

from nose.plugins.skip import SkipTest

from tests import FlexGetBase

try:
    import rarfile
except ImportError:
    rarfile = None


class TestExtract(FlexGetBase):
    __tmp__ = True
    __yaml__ = """
        templates:
            global:
                accept_all: yes
            rar_file:
                mock:
                    - {title: 'test', location: '__tmp__test.rar'}
            zip_file:
                mock:
                    - {title: 'test', location: '__tmp__test.zip'}
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

    def __init__(self):
        super(TestExtract, self).__init__()
        self.temp_rar = None
        self.temp_zip = None
        self.temp_out = None
        self.temp_out_dir = None

    def setup(self):
        super(TestExtract, self).setup()
        self.rar_name = 'test.rar'
        self.zip_name = 'test.zip'

        #archive paths
        self.temp_rar = os.path.join(self.__tmp__, self.rar_name)
        self.temp_zip = os.path.join(self.__tmp__, self.zip_name)

        # extraction paths
        self.temp_out = os.path.join(self.__tmp__, 'hooray.txt')
        self.temp_out_dir = os.path.join(self.__tmp__, 'directory', 'hooray.txt')

    def test_rar(self):
        """Test basic RAR extraction"""
        if not rarfile:
            raise SkipTest('Needs RarFile module.')
        shutil.copy(self.rar_name, self.temp_rar)
        self.execute_task('test_rar')

        assert os.path.exists(self.temp_out), 'Output file does not exist at the correct path.'
        assert os.path.exists(self.temp_rar), 'RAR archive should still exist.'

    def test_delete_rar(self):
        """Test RAR deletion after extraction"""
        if not rarfile:
            raise SkipTest('Needs RarFile module.')
        shutil.copy(self.rar_name, self.temp_rar)
        self.execute_task('test_delete_rar')

        assert not os.path.exists(self.temp_rar), 'RAR archive was not deleted.'

    def test_zip(self):
        """Test basic Zip extraction"""
        shutil.copy(self.zip_name, self.temp_zip)
        self.execute_task('test_zip')

        assert os.path.exists(self.temp_out), 'Output file does not exist at the correct path.'
        assert os.path.exists(self.temp_zip), 'Zip archive should still exist.'

    def test_keep_dirs(self):
        """Test directory creation"""
        shutil.copy(self.zip_name, self.temp_zip)
        self.execute_task('test_keep_dirs')

        assert os.path.exists(self.temp_out_dir), 'Output file does not exist at the correct path.'

    def test_delete_zip(self):
        """Test Zip deletion after extraction"""
        shutil.copy(self.zip_name, self.temp_zip)
        self.execute_task('test_delete_zip')

        assert not os.path.exists(self.temp_zip), 'Zip archive was not deleted.'
