from __future__ import unicode_literals, division, absolute_import
import os
import shutil
import imp


from tests import FlexGetBase
from tests.util import maketemp


class TestExtract(FlexGetBase):
    __yaml__ = """
        templates:
            global:
                set:
                  temp_dir: defined by setup()
                accept_all: yes
            rar_file:
                mock:
                    - {title: 'test', location: defined by setup()}
            zip_file:
                mock:
                    - {title: 'test', location: defined by setup()}
        tasks:
            test_rar:
                template: rar_file
                decompress:
                    to: '{{temp_dir}}'
                    keep_dirs: no
            test_zip:
                template: zip_file
                decompress:
                    to: '{{temp_dir}}'
                    keep_dirs: no
            test_keep_dirs:
                template: zip_file
                decompress:
                    to: '{{temp_dir}}'
                    keep_dirs: yes
            test_delete_rar:
                template: rar_file
                decompress:
                    to: '{{temp_dir}}'
                    keep_dirs: no
                    delete_archive: yes
            test_delete_zip:
                template: zip_file
                decompress:
                    to: '{{temp_dir}}'
                    keep_dirs: no
                    delete_archive: yes
                    
        """

    def __init__(self):
        super(TestExtract, self).__init__()

        try:
            imp.find_module('rarfile')
            self.rarfile_installed = True
        except ImportError:
            self.rarfile_installed = False

        self.test_home = None
        self.rar_name = None
        self.zip_name = None
        self.temp_rar = None
        self.temp_zip = None
        self.temp_out = None
        self.temp_out_dir = None


    def setup(self):
        super(TestExtract, self).setup()
        self.test_home = maketemp()

        #archive paths
        self.rar_name = 'test.rar'
        self.zip_name = 'test.zip'
        self.temp_rar = os.path.join(self.test_home, self.rar_name )
        self.temp_zip = os.path.join(self.test_home, self.zip_name)

        # extraction paths
        self.temp_out = os.path.join(self.test_home, 'hooray.txt')
        self.temp_out_dir = os.path.join(self.test_home, 'directory', 'hooray.txt')

        # set paths in config
        self.manager.config['templates']['global']['set']['temp_dir'] = self.test_home
        self.manager.config['templates']['rar_file']['mock'][0]['location'] = self.temp_rar
        self.manager.config['templates']['zip_file']['mock'][0]['location'] = self.temp_zip

#    def teardown(self):
#        # cleanup files
#        for dir, _, files in os.walk(self.test_home):
#            for file in files:
#                path = os.path.join(dir, file)
#                os.remove(path)
#        os.removedirs(self.test_home)
#
#        super(TestExtract, self).teardown()

    def test_rar(self):
        """Test basic RAR extraction"""
        # Skip RAR tests if rarfile module is missing
        if not self.rarfile_installed:
            raise SkipTest

        shutil.copy(self.rar_name, self.temp_rar)
        self.execute_task('test_rar')

        assert os.path.exists(self.temp_out)
        assert os.path.exists(self.temp_rar)

    def test_zip(self):
        """Test basic Zip extraction"""
        shutil.copy(self.rar_name, self.temp_zip)
        self.execute_task('test_zip')

        assert os.path.exists(self.temp_out)
        assert os.path.exists(self.temp_zip)

    def test_keep_dirs(self):
        """Test directory creation"""
        shutil.copy(self.rar_name, self.temp_zip)
        self.execute_task('test_keep_dirs')

        assert os.path.exists(self.temp_out_dir)

    def test_delete_rar(self):
        """Test RAR deletion after extraction"""
        # Skip RAR tests if rarfile module is missing
        if not self.rarfile_installed:
            raise SkipTest

        shutil.copy(self.rar_name, self.temp_rar)
        self.execute_task('test_delete_rar')

        assert not os.path.exists(self.temp_rar)

    def test_delete_zip(self):
        """Test Zip deletion after extraction"""
        shutil.copy(self.rar_name, self.temp_zip)
        self.execute_task('test_delete_zip')

        assert not os.path.exists(self.temp_zip)