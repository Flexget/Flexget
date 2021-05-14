from flexget import plugin
from flexget.entry import Entry

import pytest


@pytest.mark.vcr
@pytest.mark.online
class TestEmby:
    config = """
templates:
  global:
    disable:
      - remember_rejected
      - seen
      - retry_failed
      - seen_info_hash

tasks:
  emby_check_favorite:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: favorite

  emby_check_watched:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: watched

  emby_clear_favorite:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: favorite
    accept_all: yes

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: favorite

  emby_clear_watched:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: watched
    accept_all: yes

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: watched

  emby_check_list1:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: new_list_favorite

  emby_check_list2:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: new_list_watched

  emby_check_list3:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: new_list_watched_final

  emby_clear_list1:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: new_list_favorite
    accept_all: yes

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_favorite

  emby_clear_list2:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: new_list_watched
    accept_all: yes

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_watched

  emby_clear_list3:
    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: new_list_watched_final
    accept_all: yes

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_watched_final

  emby_test1:
    priority: 1
    accept_all: yes

    emby_lookup:
      host: http://emby.myhome:8096
      username: flexget
      return_host: lan
      password: flexget

    limit:
      amount: 5
      from:
        from_emby:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          types: episode
          list: TV
          sort:
            field: random
            order: descending

    list_add:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: favorite

  emby_test2:
    priority: 2
    accept_all: yes

    emby_lookup:
      host: http://emby.myhome:8096
      username: flexget
      return_host: lan
      password: flexget

    limit:
      amount: 5
      from:
        from_emby:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          types: movie
          list: Movies
          sort:
            field: random
            order: descending

    list_add:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: favorite

  emby_test3:
    priority: 3
    accept_all: yes

    emby_lookup:
      host: http://emby.myhome:8096
      username: flexget
      return_host: lan
      password: flexget

    limit:
      amount: 5
      from:
        from_emby:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: favorite
          sort:
            field: random
            order: descending

    list_add:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: watched

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: favorite

  emby_test4:
    priority: 4
    accept_all: yes

    emby_lookup:
      host: http://emby.myhome:8096
      username: flexget
      return_host: lan
      password: flexget


    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: favorite
      sort:
        field: random
        order: descending

    list_add:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_favorite

    list_remove:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: favorite

  emby_test5:
    priority: 5
    accept_all: yes

    emby_lookup:
      host: http://emby.myhome:8096
      username: flexget
      return_host: lan
      password: flexget


    from_emby:
      server:
        host: http://emby.myhome:8096
        username: flexget
        password: flexget
        return_host: lan
      list: watched
      sort:
        field: random
        order: descending

    list_add:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_watched

  emby_test6:
    priority: 6

    accept_all: yes

    limit:
      amount: 2
      from:
        from_emby:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_watched
          sort:
            field: random
            order: descending

    list_match:
      from:
        - emby_list:
            server:
              host: http://emby.myhome:8096
              username: flexget
              password: flexget
              return_host: lan
            list: watched

      action: accept
      remove_on_match: yes
      single_match: no

    list_add:
      - emby_list:
          server:
            host: http://emby.myhome:8096
            username: flexget
            password: flexget
            return_host: lan
          list: new_list_watched_final
    """

    def test_emby_clear_1(self, execute_task):
        task = execute_task('emby_clear_favorite')
        task = execute_task('emby_check_favorite')
        if len(task.all_entries) != 0:
            assert len(task.all_entries) == 0

        task = execute_task('emby_clear_watched')
        task = execute_task('emby_check_watched')
        if len(task.all_entries) != 0:
            assert len(task.all_entries) == 0

        task = execute_task('emby_clear_list1')
        task = execute_task('emby_check_list1')
        if len(task.all_entries) != 0:
            assert len(task.all_entries) == 0

        task = execute_task('emby_clear_list2')
        task = execute_task('emby_check_list2')
        if len(task.all_entries) != 0:
            assert len(task.all_entries) == 0

        task = execute_task('emby_clear_list3')
        task = execute_task('emby_check_list3')
        if len(task.all_entries) != 0:
            assert len(task.all_entries) == 0

    def test_emby_test1(self, execute_task):
        task = execute_task('emby_test1')
        assert len(task.accepted) == 5

        task = execute_task('emby_check_favorite')
        assert len(task.all_entries) == 5

    def test_emby_test2(self, execute_task):
        task = execute_task('emby_test2')
        assert len(task.accepted) == 5

        task = execute_task('emby_check_favorite')
        assert len(task.all_entries) == 10

    def test_emby_test3(self, execute_task):
        task = execute_task('emby_test3')
        assert len(task.accepted) == 5

        task = execute_task('emby_check_favorite')
        assert len(task.all_entries) == 5

        task = execute_task('emby_check_watched')
        assert len(task.all_entries) == 5

    def test_emby_test4(self, execute_task):
        task = execute_task('emby_test4')
        assert len(task.accepted) == 5

        task = execute_task('emby_check_favorite')
        assert len(task.all_entries) == 0

        task = execute_task('emby_check_list1')
        assert len(task.all_entries) == 5

    def test_emby_test5(self, execute_task):
        task = execute_task('emby_test5')
        assert len(task.accepted) == 5

        task = execute_task('emby_check_list2')
        assert len(task.all_entries) == 5

    def test_emby_test6(self, execute_task):
        task = execute_task('emby_test6')
        assert len(task.accepted) == 2

        task = execute_task('emby_check_watched')
        assert len(task.all_entries) == 3

        task = execute_task('emby_check_list3')
        assert len(task.all_entries) == 2

    def test_emby_clean(self, execute_task):
        self.test_emby_clear_1(execute_task)