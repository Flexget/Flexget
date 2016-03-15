from __future__ import unicode_literals, division, absolute_import
import re
from datetime import datetime
import pytest
from flexget.manager import Session
from flexget.plugins.api_tvdb import persist, lookup_episode, TVDBSearchResult
from flexget.plugins.input.thetvdb_favorites import TVDBUserFavorite


@pytest.mark.online
class TestTVDBLookup(object):
    config = """
        templates:
          global:
            thetvdb_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{ tvdb_id }}{{ tvdb_ep_name }}"
        tasks:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Breaking.Bad.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
            series:
              - House
              - Doctor Who 2005
          test_unknown_series:
            mock:
              - {title: 'Aoeu.Htns.S01E01.htvd'}
            series:
              - Aoeu Htns
          test_mark_expired:
            mock:
              - {title: 'House.S02E02.hdtv'}
            metainfo_series: yes
            accept_all: yes
            disable: [seen]
          test_date:
            mock:
              - title: the daily show 2012-6-6
            series:
              - the daily show (with jon stewart)
          test_absolute:
            mock:
              - title: naruto 128
            series:
              - naruto

    """

    def test_lookup(self, execute_task):
        """thetvdb: Test Lookup (ONLINE)"""
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test')

        assert task.find_entry(tvdb_ep_name='School Reunion'), 'Failed imdb lookup Doctor Who 2005 S02E03'

        entry = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['tvdb_id'] == 73255
        assert entry['tvdb_absolute_number'] == 3
        assert entry['tvdb_rating'] == 9.1
        assert entry['tvdb_runtime'] == 45
        assert entry['tvdb_season'] == 1
        assert entry['tvdb_series_name'] == 'House'
        assert entry['tvdb_status'] == 'Ended'
        assert entry['tvdb_air_time'] == ''
        assert entry['tvdb_airs_day_of_week'] == ''
        assert re.match('http://thetvdb.com/banners/graphical/73255-g[0-9]+.jpg', entry['tvdb_banner_url'])
        assert 'http://thetvdb.com/banners/posters/73255-1.jpg' in entry['tvdb_posters']
        assert entry['tvdb_content_rating'] == 'TV-14'
        assert entry['tvdb_episode'] == 2
        assert entry['tvdb_first_air_date'] == datetime(2004, 11, 16, 0, 0)
        assert entry['tvdb_network'] == 'FOX (US)'
        assert entry['tvdb_genres'] == ['Drama', 'Mystery']
        assert 'Jesse Spencer' in entry['tvdb_actors']
        assert entry['tvdb_overview'] == 'Go deeper into the medical mysteries of House, TV\'s most compelling ' \
                                         'drama. Hugh Laurie stars as the brilliant but sarcastic Dr. Gregory' \
                                         ' House, a maverick physician who is devoid of bedside manner. While' \
                                         ' his behavior can border on antisocial, Dr. House thrives on the' \
                                         ' challenge of solving the medical puzzles that other doctors give up on.' \
                                         ' Together with his hand-picked team of young medical experts, he\'ll' \
                                         ' do whatever it takes in the race against the clock to solve the case.'

        assert entry['tvdb_ep_air_date'] == datetime(2004, 11, 23, 0, 0)
        assert entry['tvdb_ep_directors'] == 'Peter O\'Fallon'
        assert entry['tvdb_ep_id'] == 'S01E02'
        assert entry['tvdb_ep_image'] == 'http://thetvdb.com/banners/episodes/73255/110995.jpg'
        assert entry['tvdb_ep_name'] == 'Paternity'
        assert entry['tvdb_ep_overview'] == 'When a teenage lacrosse player is stricken with an unidentifiable brain ' \
                                            'disease, Dr. House and the team hustle to give his parents answers. ' \
                                            'Chase breaks the bad news, the kid has MS, but the boy\'s night-terror' \
                                            ' hallucinations disprove the diagnosis and send House and his team back ' \
                                            'to square one. As the boy\'s health deteriorates. House\'s side-bet on ' \
                                            'the paternity of the patient infuriates Dr. Cuddy and the teenager\'s ' \
                                            'parents, but may just pay off in spades.'
        assert entry['tvdb_ep_rating'] == 7.8

        with Session() as session:
            # Ensure search cache was added
            search_names = [s.search for s in session.query(TVDBSearchResult).filter(TVDBSearchResult.series_id == 73255).all()]
            assert 'house' in search_names
            assert 'house m.d.' in search_names
            assert 'house md' in search_names

    def test_unknown_series(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        # Test an unknown series does not cause any exceptions
        task = execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    def test_mark_expired(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        def test_run():
            # Run the task and check tvdb data was populated.
            task = execute_task('test_mark_expired')
            entry = task.find_entry(title='House.S02E02.hdtv')
            assert entry['tvdb_ep_name'] == 'Autopsy'

        # Run the task once, this populates data from tvdb
        test_run()

        # Run the task again, this should load the data from cache
        test_run()

        # Manually mark the data as expired, to test cache update
        with Session() as session:
            ep = lookup_episode(name='House', season_number=2, episode_number=2, session=session)
            ep.expired = True
            ep.series.expired = True
            session.commit()

        test_run()

    def test_absolute(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test_absolute')
        entry = task.find_entry(title='naruto 128')
        assert entry
        assert entry['tvdb_ep_name'] == 'A Cry on Deaf Ears'


@pytest.mark.online
class TestTVDBFavorites(object):
    """
        Tests thetvdb favorites plugin with a test user at thetvdb.
        Test user info:
        username: flexget
        password: flexget
        Favorites: House, Doctor Who 2005, Penn & Teller: Bullshit, Hawaii Five-0 (2010)
    """

    config = """
        tasks:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
              - {title: 'Lost.S03E02.720p-FlexGet'}
              - {title: 'Breaking.Bad.S02E02.720p.x264'}
            configure_series:
              from:
                thetvdb_favorites:
                  username: flexget
                  password: flexget
          test_strip_dates:
            thetvdb_favorites:
              username: flexget
              password: flexget
              strip_dates: yes
    """

    def test_favorites(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test')
        assert task.find_entry('accepted', title='House.S01E02.HDTV.XViD-FlexGet'), \
            'series House should have been accepted'
        assert task.find_entry('accepted', title='Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'), \
            'series Doctor Who 2005 should have been accepted'
        assert task.find_entry('accepted', title='Breaking.Bad.S02E02.720p.x264'), \
            'series Breaking Bad should have been accepted'
        entry = task.find_entry(title='Lost.S03E02.720p-FlexGet')
        assert entry, 'Entry not found?'
        assert entry not in task.accepted, \
            'series Lost should not have been accepted'

    def test_strip_date(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test_strip_dates')
        assert task.find_entry(title='Hawaii Five-0'), \
            'series Hawaii Five-0 (2010) should have date stripped'


@pytest.mark.online
class TestTVDBSubmit(object):
    config = """
        tasks:
          add:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
            accept_all: true
            thetvdb_lookup: yes
            thetvdb_add:
              username: flexget
              password: flexget
            series:
              - House
          delete:
            mock:
              - {title: 'The.Big.Bang.Theory.S02E02.XVID-Flexget'}
            accept_all: true
            thetvdb_lookup: yes
            thetvdb_remove:
              username: flexget
              password: flexget
            series:
              - The Big Bang Theory

    """

    def test_add(self, execute_task):
        task = execute_task('add')
        task = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert task
        assert task.accepted

        with Session() as session:
            user_favs = session.query(TVDBUserFavorite).filter(TVDBUserFavorite.username == 'flexget').first()
            assert user_favs
            assert 73255 in user_favs.series_ids

    def test_delete(self, execute_task):
        with Session() as session:
            user_favs = TVDBUserFavorite(username='flexget')
            user_favs.series_ids = ['80379']
            session.add(user_favs)

        task = execute_task('delete')
        task = task.find_entry(title='The.Big.Bang.Theory.S02E02.XVID-Flexget')
        assert task
        assert task.accepted

        with Session() as session:
            user_favs = session.query(TVDBUserFavorite).filter(TVDBUserFavorite.username == 'flexget').first()
            assert user_favs
            assert 80379 not in user_favs.series_ids
