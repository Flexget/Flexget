from tests import FlexGetBase

class TestFilterSeen(FlexGetBase):
    
    __yaml__ = """
        global:
          accept_all: true

        feeds:
          test:
            input_mock:
              - {title: 'Seen title 1', url: 'http://localhost/seen1'}

          test2:
            input_mock:
              - {title: 'Seen title 2', url: 'http://localhost/seen1'} # duplicate by url
              - {title: 'Seen title 1', url: 'http://localhost/seen2'} # duplicate by title
              - {title: 'Seen title 3', url: 'http://localhost/seen3'} # new

          test_number:
            input_mock:
              - {title: 'New title 1', url: 'http://localhost/new1', imdb_score: 5}
              - {title: 'New title 2', url: 'http://localhost/new2', imdb_score: 5}
    """
    
    def test_seen(self):
        self.execute_feed('test')
        assert self.feed.find_entry(title='Seen title 1'), 'Test entry missing'
        # run again, should filter
        self.feed.execute()
        assert not self.feed.find_entry(title='Seen title 1'), 'Seen test entry remains'
            
        # execute another feed
        self.execute_feed('test2')
        # should not contain since fields seen in previous feed
        assert not self.feed.find_entry(title='Seen title 1'), 'Seen test entry 1 remains in second feed'
        assert not self.feed.find_entry(title='Seen title 2'), 'Seen test entry 2 remains in second feed'
        # new item in feed should exists
        assert self.feed.find_entry(title='Seen title 3'), 'Unseen test entry 3 not in second feed'
            
        # test that we don't filter reject on non-string fields (ie, seen same imdb_score)

        self.execute_feed('test_number')
        assert self.feed.find_entry(title='New title 1') and self.feed.find_entry(title='New title 2'), 'Item should not have been rejected because of number field'
            

class TestFilterSeenMovies(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            input_mock:
               - {title: 'Seen movie title 1', url: 'http://localhost/seen_movie1', imdb_url: 'http://www.imdb.com/title/tt0103064/'}
               - {title: 'Seen movie title 2', url: 'http://localhost/seen_movie2', imdb_url: 'http://www.imdb.com/title/tt0103064/'}
            seen_movies: true
         
          test2:
            input_mock:
              - {title: 'Seen movie title 3', url: 'http://localhost/seen_movie3', imdb_url: 'http://www.imdb.com/title/tt0103064/'}
              - {title: 'Seen movie title 4', url: 'http://localhost/seen_movie4', imdb_url: 'http://www.imdb.com/title/tt0103064/'}
              - {title: 'Seen movie title 5', url: 'http://localhost/seen_movie5', imdb_url: 'http://www.imdb.com/title/tt0231264/'}
            seen_movies: true

          strict:
            input_mock:
              - {title: 'Seen movie title 6', url: 'http://localhost/seen_movie6', imdb_url: 'http://www.imdb.com/title/tt0134532/'}
              - {title: 'Seen movie title 7', url: 'http://localhost/seen_movie7', imdb_url: 'http://www.imdb.com/title/tt0103066/'}
              - {title: 'Seen movie title 8', url: 'http://localhost/seen_movie8'}
            seen_movies: strict
    """
    
    def test_seen_movies(self):
        self.execute_feed('test')
        assert self.feed.find_entry(title='Seen movie title 1'), 'Test movie entry 1 is missing'
        # should be rejected, duplicate imdb url
        assert not self.feed.find_entry(title='Seen movie title 2'), 'Test movie entry 2 should be rejected'
        # execute again
        self.feed.execute()
        assert not self.feed.find_entry(title='Seen movie title 1'), 'Test movie entry 1 should be rejected in second execution'
        assert not self.feed.find_entry(title='Seen movie title 2'), 'Test movie entry 2 should be rejected in second execution'

        # execute another feed
        
        self.execute_feed('test2')
        # should not contain since fields seen in previous feed
        assert not self.feed.find_entry(title='Seen movie title 3'), 'seen movie 3 exists'
        assert not self.feed.find_entry(title='Seen movie title 4'), 'seen movie 4 exists'
        assert self.feed.find_entry(title='Seen movie title 5'), 'unseen movie 5 exists'
    
    def test_seen_movies_strict(self):
        self.execute_feed('strict')
        assert not self.feed.find_entry(title='Seen movie title 8'), 'strict should not have passed movie 8'
