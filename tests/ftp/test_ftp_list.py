import pytest


@pytest.mark.require_optional_deps
@pytest.mark.xdist_group(name='ftp')
class TestFtpDownload:
    def test_single_file(self, execute_task, ftpserver):
        ftpserver.reset_tmp_dirs()
        url = ftpserver.put_files('a.txt', style='url', anon=False)[0]
        login = ftpserver.get_login_data()
        config = f"""
            ftp_list:
              host: {login['host']}
              port: {login['port']}
              username: {login['user']}
              password: {login['passwd']}
            """
        task = execute_task('', config=config)
        assert len(task.all_entries) == 1
        assert task.all_entries[0]['title'] == 'a.txt'
        assert task.all_entries[0]['url'] == url

    def test_recursive(self, execute_task, ftpserver):
        ftpserver.reset_tmp_dirs()
        ftpserver.put_files({'src': 'a/b', 'dest': 'a/b'}, style='url', anon=False)
        ftpserver.put_files({'src': 'a/c/d', 'dest': 'a/c/d'}, style='url', anon=False)
        ftpserver.put_files({'src': 'a/c/e/f', 'dest': 'a/c/e/f'}, style='url', anon=False)
        login = ftpserver.get_login_data()
        config = f"""
            ftp_list:
              host: {login['host']}
              port: {login['port']}
              username: {login['user']}
              password: {login['passwd']}
              use_ssl: yes
              dirs:
                - a
              retrieve:
                - dirs
                - files
              recursion: yes
            """
        task = execute_task('', config=config)
        assert len(task.all_entries) == 5
