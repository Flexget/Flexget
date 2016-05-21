from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

try:
    import rarfile
except ImportError:
    rarfile = None


class TestArchiveFilter(object):
    config = """
        templates:
            global:
                accept_all: yes
            rar_file:
                mock:
                    - {title: 'test_rar', location: './test.rar'}
            zip_file:
                mock:
                    - {title: 'test_zip', location: './test.zip'}
            invalid_rar:
                mock:
                    - {title: 'invalid_rar', location: './fake.rar'}
            no_location:
                mock:
                    - {title: 'no_location'}
        tasks:
            test_rar:
                template: rar_file
                archives: yes
            test_zip:
                template: zip_file
                archives: yes
            test_invalid:
                template: invalid_rar
                archives: yes
            test_no_location:
                template: no_location
                archives: yes
    """

    @pytest.mark.skipif(rarfile is None, reason='rarfile module required')
    def test_rar(self, execute_task):
        """Test RAR acceptance"""
        task = execute_task('test_rar')

        assert task.find_entry('accepted', title='test_rar'), 'test.rar should have been accepted'

    def test_zip(self, execute_task):
        """Test Zip acceptance"""
        task = execute_task('test_zip')
        assert task.find_entry('accepted', title='test_zip'), 'test.zip should have been accepted'

    def test_invalid(self, execute_task):
        """Test non-archive rejection"""
        task = execute_task('test_invalid')
        assert task.find_entry('rejected', title='invalid_rar'), 'invalid_rar should have been rejected'

    def test_no_location(self, execute_task):
        """Test rejection of entries with no location"""
        task = execute_task('test_no_location')
        assert task.find_entry('rejected', title='no_location'), 'no_location should have been rejected'
