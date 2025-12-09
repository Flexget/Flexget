import filecmp
import platform
from pathlib import Path

import pytest


@pytest.mark.skipif(
    platform.system() == 'Darwin',
    reason='TODO: blocked by https://github.com/oz123/pytest-localftpserver/pull/383',
)
@pytest.mark.require_optional_deps
@pytest.mark.xdist_group(name='ftp')
class TestFtpDownload:
    def test_basic(self, execute_task, ftpserver):
        ftpserver.reset_tmp_dirs()
        url=ftpserver.put_files('a.txt', style='url', anon=False)[0]
        login = ftpserver.get_login_data()
        config = f"""
            ftp_list:
              host: {login['host']}
              port: {login['port']}
              username: {login['user']}
              password: {login['passwd']}
            """
        task=execute_task('basic', config=config)
        assert len(task.all_entries) == 1
        assert task.all_entries[0]['title'] == 'a.txt'
        assert task.all_entries[0]['url'] == url
