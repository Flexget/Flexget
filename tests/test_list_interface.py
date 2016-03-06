from __future__ import unicode_literals, division, absolute_import


class TestListInterface(object):
    config = """
        tasks:
          list_get:
            movie_list: test_list

          test_list_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent", imdb_id: "tt133434"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent", imdb_id: "tt145434"}
            list_add:
              - movie_list: test_list
    """

    def test_list_add(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2
