from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.plugins.list.pending_list import PendingListList


class TestListInterface(object):
    config = """
        templates:
          global:
            disable: [seen]

        tasks:
          list_get:
            pending_list: test_list

          pending_list_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - pending_list: test_list

          pending_list_match:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_match:
              from:
                - pending_list: test_list
    """

    def test_list_add(self, execute_task):
        task = execute_task('pending_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 0

        with Session() as session:
            list = session.query(PendingListList).first()
            assert list
            for entry in list.entries:
                entry.approved = True

        task = execute_task('list_get')
        assert len(task.entries) == 2

    def test_list_match(self, execute_task):
        task = execute_task('pending_list_add')
        assert len(task.entries) == 2

        task = execute_task('pending_list_match')
        assert len(task.accepted) == 0

        with Session() as session:
            list = session.query(PendingListList).first()
            assert list
            for entry in list.entries:
                entry.approved = True

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('pending_list_match')
        assert len(task.accepted) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 0
