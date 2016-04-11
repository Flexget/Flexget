from __future__ import unicode_literals, division, absolute_import


class TestListInterface(object):
    config = """
        templates:
          global:
            disable: [seen]

        tasks:
          list_get:
            entry_list: test_list

          list_1_get:
            entry_list: list 1

          list_2_get:
            entry_list: list 2

          test_list_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - entry_list: test_list

          list_1_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - entry_list: list 1

          list_2_add:
            mock:
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            accept_all: yes
            list_add:
              - entry_list: list 2

          test_multiple_list_add:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
            accept_all: yes
            list_add:
              - entry_list: list 1
              - entry_list: list 2

          test_list_accept_with_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              - entry_list: test_list

          test_list_accept_without_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              lists:
                - entry_list: test_list
              remove_on_accept: no

          test_multiple_list_accept_with_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              - entry_list: list 1
              - entry_list: list 2

          test_multiple_list_accept_without_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 2', url: "http://mock.url/file2.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_accept:
              lists:
                - entry_list: list 1
                - entry_list: list 2
              remove_on_accept: no

          test_list_remove:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
            accept_all: yes
            list_remove:
              - entry_list: test_list

          test_list_reject:
            mock:
              - {title: 'title 1', url: "http://mock.url/file1.torrent"}
              - {title: 'title 3', url: "http://mock.url/file3.torrent"}
            list_reject:
              - entry_list: test_list

          add_for_list_queue:
            mock:
              - {title: 'The 5th Wave', url: "", imdb_id: "tt2304933"}
              - {title: 'Drumline', url: "", imdb_id: "tt0303933"}
            accept_all: yes
            list_add:
              - movie_list: test_list_queue

          test_list_queue:
            mock:
              - {title: 'The 5th Wave 2016 720p BluRay DTS x264-FuzerHD', url: "http://mock.url/The 5th Wave 2016 720p BluRay DTS x264-FuzerHD.torrent", imdb_id: "tt2304933"}
              - {title: 'The 5th Wave 2016 1080p BluRay DTS x264-FuzerHD', url: "http://mock.url/The 5th Wave 2016 1080p BluRay DTS x264-FuzerHD.torrent", imdb_id: "tt2304933"}
              - {title: 'The 5th Wave 2016 DVDRip x264-FuzerHD', url: "http://mock.url/The 5th Wave 2016 DVDRip x264-FuzerHD.torrent", imdb_id: "tt2304933"}
              - {title: 'Drumline 2002 1080p BluRay DTS-HD MA 5 1 x264-FuzerHD', url: "http://mock.url/Drumline 2002 1080p BluRay DTS-HD MA 5 1 x264-FuzerHD.torrent", imdb_id: "tt0303933"}
              - {title: 'Drumline 2002 720p BluRay DTS-HD MA 5 1 x264-FuzerHD', url: "http://mock.url/Drumline 2002 720p BluRay DTS-HD MA 5 1 x264-FuzerHD.torrent", imdb_id: "tt0303933"}
              - {title: 'Drumline 2002 DVDRip x264-FuzerHD', url: "http://mock.url/Drumline 2002 DVDRip x264-FuzerHD.torrent", imdb_id: "tt0303933"}
            list_queue:
              - movie_list: test_list_queue

          get_for_list_queue:
             movie_list: test_list_queue
    """

    def test_list_add(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

    def test_multiple_list_add(self, execute_task):
        task = execute_task('test_multiple_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 2

    def test_list_accept_with_remove(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_accept_with_remove')
        assert len(task.all_entries) == 3
        assert len(task.accepted) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 0

    def test_list_accept_without_remove(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_accept_without_remove')
        assert len(task.all_entries) == 3
        assert len(task.accepted) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

    def test_multiple_list_accept_with_remove(self, execute_task):
        task = execute_task('list_1_add')
        assert len(task.entries) == 2

        task = execute_task('list_2_add')
        assert len(task.entries) == 1

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 1

        task = execute_task('test_multiple_list_accept_with_remove')
        assert len(task.accepted) == 3

        task = execute_task('list_1_get')
        assert len(task.entries) == 0

        task = execute_task('list_2_get')
        assert len(task.entries) == 0

    def test_multiple_list_accept_without_remove(self, execute_task):
        task = execute_task('list_1_add')
        assert len(task.entries) == 2

        task = execute_task('list_2_add')
        assert len(task.entries) == 1

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 1

        task = execute_task('test_multiple_list_accept_without_remove')
        assert len(task.accepted) == 3

        task = execute_task('list_1_get')
        assert len(task.entries) == 2

        task = execute_task('list_2_get')
        assert len(task.entries) == 1

    def test_list_remove(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_remove')
        assert len(task.accepted) == 1

        task = execute_task('list_get')
        assert len(task.entries) == 1

    def test_list_reject(self, execute_task):
        task = execute_task('test_list_add')
        assert len(task.entries) == 2

        task = execute_task('list_get')
        assert len(task.entries) == 2

        task = execute_task('test_list_reject')
        assert len(task.rejected) == 1

    def test_list_queue(self, execute_task):
        # List queue test is based off movie_list and not entry_list since it entry_list matching is a
        # lot more strict so it doesn't make sense to use it with it
        task = execute_task('add_for_list_queue')
        assert len(task.entries) == 2

        task = execute_task('test_list_queue')
        assert len(task.accepted) == 2

        assert task.find_entry(title="The 5th Wave 2016 720p BluRay DTS x264-FuzerHD")
        assert task.find_entry(title="Drumline 2002 1080p BluRay DTS-HD MA 5 1 x264-FuzerHD")

        task = execute_task('get_for_list_queue')
        assert len(task.entries) == 0
