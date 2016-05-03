from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import re
from datetime import datetime, timedelta

import mock
import pytest

from flexget.manager import Session
from flexget.plugins.api_tvdb import persist, TVDBSearchResult, lookup_series, mark_expired, TVDBRequest, TVDBEpisode, find_series_id
from flexget.plugins.input.thetvdb_favorites import TVDBUserFavorite


@mock.patch('flexget.plugins.api_tvdb.mark_expired')
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
          test_search_cache:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
            series:
              - House
          test_unknown_series:
            mock:
              - {title: 'Aoeu.Htns.S01E01.htvd'}
            series:
              - Aoeu Htns
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
          test_no_poster_actors:
            mock:
              - {title: 'Sex.House.S01E02.HDTV.XViD-FlexGet'}
            series:
              - Sex House
              - The Blacklist

    """

    def test_lookup(self, mocked_expired, execute_task):
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
        assert re.match('http://thetvdb.com/banners/graphical/73255-g[0-9]+.jpg', entry['tvdb_banner'])
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

    def test_no_posters_actors(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test_no_poster_actors')
        entry = task.find_entry(tvdb_series_name='Sex House')
        assert entry['tvdb_posters'] == []
        assert entry['tvdb_actors'] == []

    def test_cache(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test_search_cache')
        entry = task.find_entry(tvdb_id=73255)

        # Force tvdb lazy eval
        assert entry['afield']

        with Session() as session:
            # Ensure search cache was added
            search_results = session.query(TVDBSearchResult).all()

            assert len(search_results) == 3

            aliases = ['house', 'house m.d.', 'house md']

            for search_result in search_results:
                assert search_result.series
                assert search_result.search in aliases

            # No requests should be sent as we restore from cache
            with mock.patch('requests.sessions.Session.request',
                            side_effect=Exception('TVDB should restore from cache')) as _:
                lookup_series('house m.d.', session=session)

    def test_unknown_series(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

        # Test an unknown series does not cause any exceptions
        task = execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    def test_absolute(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test_absolute')
        entry = task.find_entry(title='naruto 128')
        assert entry
        assert entry['tvdb_ep_name'] == 'A Cry on Deaf Ears'

    def test_find_series_id(self, mocked_expired, execute_task):
        # Test the best match logic
        assert find_series_id('Once Upon A Time') == 248835
        assert find_series_id('Once Upon A Time 2011') == 248835
        assert find_series_id('House M.D.') == 73255
        assert find_series_id('House') == 73255


@pytest.mark.online
class TestTVDBExpire(object):
    config = """
        templates:
          global:
            thetvdb_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{ tvdb_id }}{{ tvdb_ep_name }}"
        tasks:
          test_mark_expired:
            mock:
              - {title: 'House.S02E02.hdtv'}
            metainfo_series: yes
            accept_all: yes
            disable: [seen]
    """

    def test_expire_no_check(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        def test_run():
            # Run the task and check tvdb data was populated.
            task = execute_task('test_mark_expired')
            entry = task.find_entry(title='House.S02E02.hdtv')
            assert entry['tvdb_ep_name'] == 'Autopsy'

        # Run the task once, this populates data from tvdb
        test_run()

        # Should not expire as it was checked less then an hour ago
        persist['last_check'] = datetime.utcnow() - timedelta(hours=1)
        with mock.patch('requests.sessions.Session.request',
                        side_effect=Exception('Tried to expire or lookup, less then an hour since last check')) as _:
            # Ensure series is not marked as expired
            with Session() as session:
                mark_expired(session)
                ep = session.query(TVDBEpisode)\
                    .filter(TVDBEpisode.series_id == 73255)\
                    .filter(TVDBEpisode.episode_number == 2)\
                    .filter(TVDBEpisode.season_number == 2)\
                    .first()
                assert not ep.expired
                assert not ep.series.expired

    def test_expire_check(self, execute_task):
        persist['auth_tokens'] = {'default': None}

        def test_run():
            # Run the task and check tvdb data was populated.
            task = execute_task('test_mark_expired')
            entry = task.find_entry(title='House.S02E02.hdtv')
            assert entry['tvdb_ep_name'] == 'Autopsy'

        # Run the task once, this populates data from tvdb
        test_run()

        # Should expire
        persist['last_check'] = datetime.utcnow() - timedelta(hours=3)

        expired_data = [
            {
                "id": 73255,
                "lastUpdated": 1458186055
            },
            {
                "id": 295743,
                "lastUpdated": 1458186088
            }
        ]

        # Ensure series is marked as expired
        with mock.patch.object(TVDBRequest, 'get', side_effect=[expired_data]) as _:
            with Session() as session:
                mark_expired(session)
                ep = session.query(TVDBEpisode)\
                    .filter(TVDBEpisode.series_id == 73255)\
                    .filter(TVDBEpisode.episode_number == 2)\
                    .filter(TVDBEpisode.season_number == 2)\
                    .first()
                assert ep.expired
                assert ep.series.expired

        # Run the task again, should be re-populated from tvdb
        test_run()

        with Session() as session:
            ep = session.query(TVDBEpisode)\
                .filter(TVDBEpisode.series_id == 73255)\
                .filter(TVDBEpisode.episode_number == 2)\
                .filter(TVDBEpisode.season_number == 2)\
                .first()
            assert not ep.expired
            assert not ep.series.expired


@mock.patch('flexget.plugins.api_tvdb.mark_expired')
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
                  account_id: 80FB8BD0720CA5EC
          test_strip_dates:
            thetvdb_favorites:
              username: flexget
              account_id: 80FB8BD0720CA5EC
              strip_dates: yes
    """

    def test_favorites(self, mocked_expired, execute_task):
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

        with Session() as session:
            user = session.query(TVDBUserFavorite).filter(TVDBUserFavorite.username == 'flexget').first()
            assert user
            assert len(user.series_ids) > 0
            assert user.series_ids == [78804, 84946, 164541, 73255, 81189]

    def test_strip_date(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('test_strip_dates')
        assert task.find_entry(title='Hawaii Five-0'), \
            'series Hawaii Five-0 (2010) should have date stripped'


@mock.patch('flexget.plugins.api_tvdb.mark_expired')
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
              account_id: 80FB8BD0720CA5EC
            series:
              - House
          delete:
            mock:
              - {title: 'The.Big.Bang.Theory.S02E02.XVID-Flexget'}
            accept_all: true
            thetvdb_lookup: yes
            thetvdb_remove:
              username: flexget
              account_id: 80FB8BD0720CA5EC
            series:
              - The Big Bang Theory

    """

    def test_add(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

        task = execute_task('add')
        task = task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert task
        assert task.accepted

        with Session() as session:
            user_favs = session.query(TVDBUserFavorite).filter(TVDBUserFavorite.username == 'flexget').first()
            assert user_favs
            assert 73255 in user_favs.series_ids

    def test_delete(self, mocked_expired, execute_task):
        persist['auth_tokens'] = {'default': None}

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
