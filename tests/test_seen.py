class TestFilterSeen:
    config = """
        templates:
          global:
            accept_all: true

        tasks:
          test:
            mock:
              - {title: 'Seen title 1', url: 'http://localhost/seen1'}

          test2:
            mock:
              - {title: 'Seen title 2', url: 'http://localhost/seen1'} # duplicate by url
              - {title: 'Seen title 1', url: 'http://localhost/seen2'} # duplicate by title
              - {title: 'Seen title 3', url: 'http://localhost/seen3'} # new

          test_number:
            mock:
              - {title: 'New title 1', url: 'http://localhost/new1', imdb_score: 5}
              - {title: 'New title 2', url: 'http://localhost/new2', imdb_score: 5}

          test_learn:
            mock:
            - title: learned entry
            accept_all: yes
            mock_output: yes
    """

    def test_seen(self, execute_task):
        task = execute_task('test')
        assert task.find_entry(title='Seen title 1'), 'Test entry missing'
        # run again, should filter
        task = execute_task('test')
        assert not task.find_entry(title='Seen title 1'), 'Seen test entry remains'

        # execute another task
        task = execute_task('test2')
        # should not contain since fields seen in previous task
        assert not task.find_entry(title='Seen title 1'), (
            'Seen test entry 1 remains in second task'
        )
        assert not task.find_entry(title='Seen title 2'), (
            'Seen test entry 2 remains in second task'
        )
        # new item in task should exists
        assert task.find_entry(title='Seen title 3'), 'Unseen test entry 3 not in second task'

        # test that we don't filter reject on non-string fields (ie, seen same imdb_score)

        task = execute_task('test_number')
        assert task.find_entry(title='New title 1'), (
            'Item should not have been rejected because of number field'
        )
        assert task.find_entry(title='New title 2'), (
            'Item should not have been rejected because of number field'
        )

    def test_learn(self, execute_task):
        task = execute_task('test_learn', options={'learn': True})
        assert len(task.accepted) == 1, 'entry should have been accepted'
        assert not task.mock_output, 'Entry should not have been output with --learn'
        task = execute_task('test_learn')
        assert len(task.rejected) == 1, 'Seen plugin should have rejected on second run'


class TestSeenLocal:
    config = """
      templates:
        global:
          accept_all: yes
      tasks:
        global seen 1:
          mock:
          - title: item 1
        local seen:
          seen: local
          mock:
          - title: item 1
          - title: item 2
        global seen 2:
          mock:
          - title: item 1
          - title: item 2
        local seen 2:
          seen:
            local: yes
          mock:
          - title: item 1
          - title: item 2
    """

    def test_local(self, execute_task):
        task = execute_task('global seen 1')
        # global seen 1 task should not affect seen in the local seen task
        task = execute_task('local seen')
        assert task.find_entry('accepted', title='item 1'), 'item 1 should be accepted first run'
        # seen should still work normally within the local seen task
        task = execute_task('local seen')
        assert task.find_entry('rejected', title='item 1'), 'item 1 should be seen on second run'
        # local seen task should not affect global seen 2 task, but global seen 1 should
        task = execute_task('global seen 2')
        assert task.find_entry('rejected', title='item 1'), 'item 1 should be seen'
        assert task.find_entry('accepted', title='item 2'), 'item 2 should be accepted'

    def test_local_dict_config(self, execute_task):
        task = execute_task('local seen 2')
        assert task.find_entry('accepted', title='item 1'), 'item 1 should be accepted'
        assert task.find_entry('accepted', title='item 2'), 'item 2 should be accepted'

        task = execute_task('global seen 2')
        assert task.find_entry('accepted', title='item 1'), 'item 1 should be accepted'
        assert task.find_entry('accepted', title='item 2'), 'item 2 should be accepted'

        task = execute_task('local seen 2')
        assert task.find_entry('rejected', title='item 1'), 'item 1 should be seen'
        assert task.find_entry('rejected', title='item 2'), 'item 2 should be seen'


class TestFilterSeenMovies:
    config = """
        tasks:
          test_1:
            mock:
               - {title: 'Seen movie title 1', url: 'http://localhost/seen_movie1', imdb_id: 'tt0103064', tmdb_id: 123}
               - {title: 'Seen movie title 2', url: 'http://localhost/seen_movie2', imdb_id: 'tt0103064'}
            accept_all: yes
            seen_movies: loose

          test_2:
            mock:
              - {title: 'Seen movie title 3', url: 'http://localhost/seen_movie3', imdb_id: 'tt0103064'}
              - {title: 'Seen movie title 4', url: 'http://localhost/seen_movie4', imdb_id: 'tt0103064'}
              - {title: 'Seen movie title 5', url: 'http://localhost/seen_movie5', imdb_id: 'tt0231264'}
              - {title: 'Seen movie title 6', url: 'http://localhost/seen_movie6', tmdb_id: 123}
              - {title: 'Seen movie title 13', url: 'http://localhost/seen_movie13', imdb_id: 'tt9901062'}
            seen_movies: loose

          strict:
            mock:
              - {title: 'Seen movie title 7', url: 'http://localhost/seen_movie7', imdb_id: 'tt0134532'}
              - {title: 'Seen movie title 8', url: 'http://localhost/seen_movie8', imdb_id: 'tt0103066'}
              - {title: 'Seen movie title 9', url: 'http://localhost/seen_movie9', tmdb_id: 456}
              - {title: 'Seen movie title 10', url: 'http://localhost/seen_movie10'}
            seen_movies: strict

          local:
            mock:
              - {title: 'Seen movie title 11', url: 'http://localhost/seen_movie11', imdb_id: 'tt0103064', tmdb_id: 123}
              - {title: 'Seen movie title 12', url: 'http://localhost/seen_movie12', imdb_id: 'tt9901062'}
            accept_all: yes
            seen_movies:
              scope: local
    """

    def test_seen_movies(self, execute_task):
        task = execute_task('test_1')
        assert not (
            task.find_entry(title='Seen movie title 1')
            and task.find_entry(title='Seen movie title 2')
        ), 'Movie accepted twice in one run'

        # execute again
        task = execute_task('test_1')
        assert not task.find_entry(title='Seen movie title 1'), (
            'Test movie entry 1 should be rejected in second execution'
        )
        assert not task.find_entry(title='Seen movie title 2'), (
            'Test movie entry 2 should be rejected in second execution'
        )

        # execute another task
        task = execute_task('test_2')

        # should not contain since fields seen in previous task
        assert not task.find_entry(title='Seen movie title 3'), 'seen movie 3 exists'
        assert not task.find_entry(title='Seen movie title 4'), 'seen movie 4 exists'
        assert not task.find_entry(title='Seen movie title 6'), 'seen movie 6 exists (tmdb_id)'
        assert task.find_entry(title='Seen movie title 5'), 'unseen movie 5 doesn\'t exist'

    def test_seen_movies_strict(self, execute_task):
        task = execute_task('strict')
        assert len(task.rejected) == 1, 'Too many movies were rejected'
        assert not task.find_entry(title='Seen movie title 10'), (
            'strict should not have passed movie 10'
        )

    def test_seen_movies_local(self, execute_task):
        task = execute_task('local')
        assert task.find_entry('accepted', title='Seen movie title 11'), (
            'local should have passed movie 11'
        )
        # execute again
        task = execute_task('local')
        msg = 'Test movie entry 12 should be rejected in second execution'
        assert task.find_entry('rejected', title='Seen movie title 12'), msg
        # test a global scope after
        task = execute_task('test_2')
        msg = 'Changing scope should not have rejected Seen movie title 13'
        assert not task.find_entry('rejected', title='Seen movie title 13'), msg
