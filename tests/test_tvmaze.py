from datetime import datetime, timedelta

import pytest

from flexget.components.tvmaze.api_tvmaze import (
    APITVMaze,
    TVMazeEpisodes,
    TVMazeLookup,
    TVMazeSeries,
)
from flexget.manager import Session

lookup_series = APITVMaze.series_lookup


@pytest.mark.online
class TestTVMazeShowLookup:
    config = """
        templates:
          global:
            tvmaze_lookup: yes
            set:
              afield: "{{tvdb_id}}{{tvmaze_episode_name}}{{tvmaze_series_name}}"
        tasks:
          test:
            mock:
              - {title: 'House.MD.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.S02E03.PDTV.XViD-FlexGet'}
            series:
              - House MD
              - Doctor Who
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
          test_search_result:
            mock:
              - {title: 'Shameless.2011.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Shameless.2011.S03E02.HDTV.XViD-FlexGet'}
            series:
              - Shameless (2011)
          test_title_with_year:
            mock:
              - {title: 'The.Flash.2014.S02E06.HDTV.x264-FlexGet'}
            series:
              - The Flash (2014)
          test_from_filesystem:
            filesystem:
              path: tvmaze_test_dir/
              recursive: yes
            series:
              - The Walking Dead
              - The Big Bang Theory
              - Marvels Jessica Jones
              - The Flash (2014)
          test_series_expiration:
            mock:
              - {title: 'Shameless.2011.S03E02.HDTV.XViD-FlexGet'}
            series:
              - Shameless (2011)
          test_show_is_number:
            mock:
              - {title: '1992.S01E02.720p.HDTV.XViD-FlexGet'}
              - {title: '24 S01E01 HDTV x264-FlexGet'}
            series:
              - 1992
              - 24
          test_show_contain_number:
            mock:
              - {title: 'Tosh.0 S07E30 HDTV x264-FlexGet'}
              - {title: 'Unwrapped 2.0 S02E06 HDTV x264-FlexGet'}
              - {title: 'Detroit 1-8-7 S01E16 HDTV x264-FlexGet'}
              - {title: 'Jake 2.0 S01E10 HDTV x264-FlexGet'}
            series:
              - Detroit 1-8-7
              - Jake 2.0
              - Unwrapped 2.0
              - Tosh.0
          test_episode_without_air_date:
            mock:
              - {title: 'Firefly S01E13 HDTV x264-FlexGet'}
            series:
              - Firefly
            set:
              bfield: "{{tvmaze_episode_airdate}}{{tvmaze_episode_airstamp}}"
          test_episode_summary:
            mock:
              - {title: 'The.Flash.2014.S02E02.HDTV.x264-FlexGet'}
            series:
              - The Flash
          test_show_with_non_ascii_chars:
            mock:
              - {title: 'Unite 9 S01E16 VFQ HDTV XviD-FlexGet'}
            series:
              - Unite 9
          test_show_cast:
            mock:
              - {title: 'The.Flash.2014.S02E02.HDTV.x264-FlexGet'}
            series:
              - The Flash
          test_multiple_characters_per_actor:
            mock:
              - {title: 'Californication.S01E01.HDTV.x264-FlexGet'}
              - {title: 'The.X-Files.S01E01.HDTV.x264-FlexGet'}
              - {title: 'Aquarius.US.S01E1.HDTV.x264-FlexGet'}
            series:
              - Californication
              - The X-Files
              - Aquarius
          test_episode_air_date:
            mock:
              - {title: 'The.Flash.2014.S02E02.HDTV.x264-FlexGet'}
            series:
              - The Flash
          test_queries_via_ids:
            mock:
              - {title: 'The.Flash.2014.S02E02.HDTV.x264-FlexGet', tvmaze_id: '13'}
              - {title: 'The.Flash.2014.S02E03.HDTV.x264-FlexGet', tvdb_id: '279121'}
              - {title: 'The.Flash.2014.S02E04.HDTV.x264-FlexGet', imdb_id: 'tt3107288'}
            series:
              - The Flash
          test_ep_mixup_error:
            mock:
              - {title: 'The.Flash.2014.S02E02.HDTV.x264-FlexGet'}
              - {title: 'The.Arrow.S02E02.HDTV.x264-FlexGet'}
            metainfo_series: yes
    """

    def test_lookup_name(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='House.MD.S01E02.HDTV.XViD-FlexGet')
        assert entry['tvmaze_series_id'] == 118, 'Tvmaze_ID should be 118 is {} for {}'.format(
            entry['tvmaze_series_name'],
            entry['series_name'],
        )
        assert entry['tvmaze_series_status'] == 'Ended', (
            'Series Status should be "ENDED" returned {}'.format(entry['tvmaze_series_status'])
        )

    def test_lookup(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='House.MD.S01E02.HDTV.XViD-FlexGet')
        assert entry['tvmaze_episode_name'] == 'Paternity', (
            '{} tvmaze_episode_name should be Paternity, is actually {}'.format(
                entry['title'],
                entry['tvmaze_episode_name'],
            )
        )
        assert entry['tvmaze_series_status'] == 'Ended', (
            'status for {} is {}, should be "ended"'.format(
                entry['title'],
                entry['tvmaze_series_status'],
            )
        )
        assert entry['afield'] == '73255PaternityHouse', (
            'afield was not set correctly, expected 73255PaternityHouse M.D., got {}'.format(
                entry['afield']
            )
        )
        assert task.find_entry(tvmaze_episode_name='School Reunion'), (
            'Failed imdb lookup Doctor Who 2005 S02E03'
        )

    def test_unknown_series(self, execute_task):
        # Test an unknown series does not cause any exceptions
        task = execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    def test_search_results(self, execute_task):
        task = execute_task('test_search_result')
        entry = task.entries[0]
        print(entry['tvmaze_series_name'].lower())
        assert entry['tvmaze_series_name'].lower() == 'Shameless'.lower(), 'lookup failed'
        with Session() as session:
            assert task.entries[1]['tvmaze_series_name'].lower() == 'Shameless'.lower(), (
                'second lookup failed'
            )

            assert len(session.query(TVMazeLookup).all()) == 1, (
                'should have added 1 show to search result'
            )

            assert len(session.query(TVMazeSeries).all()) == 1, (
                'should only have added one show to show table'
            )
            assert session.query(TVMazeSeries).first().name == 'Shameless', (
                'should have added Shameless and not Shameless (2011)'
            )
            # change the search query
            session.query(TVMazeLookup).update({'search_name': "shameless.s01e03.hdtv-flexget"})
            session.commit()

            lookupargs = {'title': "Shameless.S01E03.HDTV-FlexGet"}
            series = APITVMaze.series_lookup(**lookupargs)

            assert series.tvdb_id == entry['tvdb_id'], (
                'tvdb id should be the same as the first entry'
            )
            assert series.tvmaze_id == entry['tvmaze_series_id'], (
                'tvmaze id should be the same as the first entry'
            )
            assert series.name.lower() == entry['tvmaze_series_name'].lower(), (
                'series name should match first entry'
            )

    def test_date(self, execute_task):
        task = execute_task('test_date')
        entry = task.find_entry(title='the daily show 2012-6-6')
        assert entry.get('tvmaze_series_id') == 249, (
            'expected tvmaze_series_id 249, got {}'.format(entry.get('tvmaze_series_id'))
        )
        assert entry.get('tvmaze_episode_id') == 20471, (
            'episode id should be 20471, is actually {}'.format(entry.get('tvmaze_episode_id'))
        )

    def test_title_with_year(self, execute_task):
        task = execute_task('test_title_with_year')
        entry = task.find_entry(title='The.Flash.2014.S02E06.HDTV.x264-FlexGet')
        assert entry.get('tvmaze_series_id') == 13, 'expected tvmaze_series_id 13, got {}'.format(
            entry.get('tvmaze_series_id')
        )
        assert entry.get('tvmaze_series_year') == 2014, (
            'expected tvmaze_series_year 2014, got {}'.format(entry.get('tvmaze_series_year'))
        )

    def test_from_filesystem(self, execute_task):
        task = execute_task('test_from_filesystem')
        entry = task.find_entry(
            title='Marvels.Jessica.Jones.S01E02.PROPER.720p.WEBRiP.x264-FlexGet'
        )
        assert entry.get('tvmaze_series_id') == 1370, (
            'expected tvmaze_series_id 1370, got {}'.format(entry.get('tvmaze_series_id'))
        )
        assert entry.get('tvmaze_episode_id') == 206178, (
            'episode id should be 206178, is actually {}'.format(entry.get('tvmaze_episode_id'))
        )
        entry = task.find_entry(title='Marvels.Jessica.Jones.S01E03.720p.WEBRiP.x264-FlexGet')
        assert entry.get('tvmaze_series_id') == 1370, (
            'expected tvmaze_series_id 1370, got {}'.format(entry.get('tvmaze_series_id'))
        )
        assert entry.get('tvmaze_episode_id') == 206177, (
            'episode id should be 206177, is actually {}'.format(entry.get('tvmaze_episode_id'))
        )
        entry = task.find_entry(title='The.Big.Bang.Theory.S09E09.720p.HDTV.X264-FlexGet')
        assert entry.get('tvmaze_series_id') == 66, 'expected tvmaze_series_id 66, got {}'.format(
            entry.get('tvmaze_series_id')
        )
        assert entry.get('tvmaze_episode_id') == 409180, (
            'episode id should be 409180, is actually {}'.format(entry.get('tvmaze_episode_id'))
        )
        entry = task.find_entry(title='The.Flash.S02E04.1080p.WEB-DL.DD5.1.H.264-FlexGet')
        assert entry.get('tvmaze_series_id') == 13, 'expected tvmaze_series_id 13, got {}'.format(
            entry.get('tvmaze_series_id')
        )
        assert entry.get('tvmaze_episode_id') == 284974, (
            'episode id should be 284974, is actually {}'.format(entry.get('tvmaze_episode_id'))
        )
        entry = task.find_entry(title='The.Walking.Dead.S06E08.Start.to.Finish-FlexGet')
        assert entry.get('tvmaze_series_id') == 73, 'expected tvmaze_series_id 73, got {}'.format(
            entry.get('tvmaze_series_id')
        )
        assert entry.get('tvmaze_episode_id') == 185073, (
            'episode id should be 185073, is actually {}'.format(entry.get('tvmaze_episode_id'))
        )

    def test_series_expiration(self, execute_task):
        task = execute_task('test_series_expiration')
        entry = task.entries[0]
        assert entry['tvmaze_series_name'].lower() == 'Shameless'.lower(), 'lookup failed'
        assert entry['tvmaze_episode_id'] == 11134, (
            'episode id should be 11134, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        with Session() as session:
            # Manually change a value of the series to differ from actual value
            assert session.query(TVMazeSeries).first().name == 'Shameless', (
                'should have added Shameless and not Shameless (2011)'
            )
            session.query(TVMazeSeries).update({'runtime': 100})
            session.commit()

            # Verify value has changed successfully and series expiration status is still False
            assert not session.query(TVMazeSeries).first().expired, (
                'expired status should be False'
            )
            assert session.query(TVMazeSeries).first().runtime == 100, 'should be updated to 99'

            # Set series last_update time to 8 days ago, to trigger a show refresh upon request.
            last_week = datetime.now() - timedelta(
                days=8
            )  # Assuming max days between refreshes is 7
            session.query(TVMazeSeries).update({'last_update': last_week})
            session.commit()

            # Verify series expiration flag is now True
            assert session.query(TVMazeSeries).first().expired, 'expired status should be True'

            lookupargs = {'title': "Shameless"}
            series = APITVMaze.series_lookup(**lookupargs)

            # Verify series data has been refreshed with actual values upon 2nd call, and series expiration flag
            # is set to False
            assert series.runtime == 60, (
                f'runtime should have been updated back to 60 from 100, instead its {series.runtime}'
            )
            assert not session.query(TVMazeSeries).first().expired, (
                'expired status should be False'
            )

    def test_test_show_is_number(self, execute_task):
        task = execute_task('test_show_is_number')
        entry = task.find_entry(series_name='1992')
        assert entry['tvmaze_series_name'] == '1992', 'lookup failed'
        assert entry['tvmaze_series_id'] == 4879, (
            'series id should be 4879, instead its {}'.format(entry['tvmaze_series_id'])
        )
        assert entry['tvmaze_episode_id'] == 308487, (
            'episode id should be 308487, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        entry = task.find_entry(series_name='24')
        assert entry['tvmaze_series_name'] == '24'.lower(), 'lookup failed'
        assert entry['tvmaze_series_id'] == 167, 'series id should be 167, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 11891, (
            'episode id should be 11891, instead its {}'.format(entry['tvmaze_episode_id'])
        )

    def test_show_contain_number(self, execute_task):
        task = execute_task('test_show_contain_number')
        entry = task.find_entry(series_name='Tosh.0')
        assert entry['tvmaze_series_name'] == 'Tosh.0', (
            'tvmaze_series_name should be Tosh.0, instead its {}'.format(
                entry['tvmaze_series_name']
            )
        )
        assert entry['tvmaze_series_id'] == 260, 'series id should be 260, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 457679, (
            'episode id should be 457679, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        entry = task.find_entry(series_name='Unwrapped 2.0')
        assert entry['tvmaze_series_name'] == 'Unwrapped 2.0', (
            'tvmaze_series_name should be Unwrapped 2.0, instead its {}'.format(
                entry['tvmaze_series_name']
            )
        )
        assert entry['tvmaze_series_id'] == 5736, (
            'series id should be 5736, instead its {}'.format(entry['tvmaze_series_id'])
        )
        assert entry['tvmaze_episode_id'] == 387214, (
            'episode id should be 387214, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        entry = task.find_entry(series_name='Jake 2.0')
        assert entry['tvmaze_series_name'] == 'Jake 2.0', (
            'tvmaze_series_name should be Jake 2.0, instead its {}'.format(
                entry['tvmaze_series_name']
            )
        )
        assert entry['tvmaze_series_id'] == 2381, (
            'series id should be 2381, instead its {}'.format(entry['tvmaze_series_id'])
        )
        assert entry['tvmaze_episode_id'] == 184265, (
            'episode id should be 184265, instead its {}'.format(entry['tvmaze_episode_id'])
        )

    def test_episode_without_air_date_and_air_stamp(self, execute_task):
        task = execute_task('test_episode_without_air_date')

        entry = task.find_entry(title='Firefly S01E13 HDTV x264-FlexGet')
        assert entry['tvmaze_series_id'] == 180, 'series id should be 180, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 13007, (
            'episode id should be 13007, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        assert entry['tvmaze_episode_airdate'] is None, (
            'Expected airdate to be None, got {}'.format(entry['tvmaze_episode_airdate'])
        )
        assert entry['tvmaze_episode_airstamp'] is None, (
            'Expected airdate to be None, got {}'.format(entry['tvmaze_episode_airstamp'])
        )

    def test_episode_summary(self, execute_task):
        expected_summary = (
            "<p>The team's visitor, Jay Garrick, explains that he comes from a parallel world and "
            "was a speedster there, but lost his powers transitioning over. Now he insists that Barry"
            " needs his help fighting a new metahuman, Sand Demon, who came from Jay's world."
            " Meanwhile, Officer Patty Spivot tries to join Joe's Metahuman Taskforce.</p>"
        )

        task = execute_task('test_episode_summary')
        entry = task.entries[0]
        assert entry['tvmaze_series_id'] == 13, 'series id should be 13, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 211206, (
            'episode id should be 211206, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        assert entry['tvmaze_episode_summary'] == expected_summary, (
            'Expected summary is different {}'.format(entry['tvmaze_episode_summary'])
        )

    def test_show_with_non_ascii_chars(self, execute_task):
        task = execute_task('test_show_with_non_ascii_chars')
        entry = task.entries[0]
        assert entry['tvmaze_series_name'] == 'Unit\xe9 9', (
            'series id should be Unit\xe9 9, instead its {}'.format(entry['tvmaze_series_name'])
        )
        assert entry['tvmaze_series_id'] == 8652, (
            'series id should be 8652, instead its {}'.format(entry['tvmaze_series_id'])
        )
        assert entry['tvmaze_episode_id'] == 476294, (
            'episode id should be 476294, instead its {}'.format(entry['tvmaze_episode_id'])
        )

    def test_episode_air_date(self, execute_task):
        task = execute_task('test_episode_air_date')
        entry = task.entries[0]
        assert entry['tvmaze_series_id'] == 13, 'series id should be 13, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 211206, (
            'episode id should be 211206, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        assert isinstance(entry['tvmaze_episode_airdate'], datetime), (
            'expected to received datetime type'
        )
        airdate = datetime.strftime(entry['tvmaze_episode_airdate'], '%Y-%m-%d')
        assert airdate == '2015-10-13', (
            f'episode airdate should be 2015-10-13, instead its {airdate}'
        )

    def test_queries_via_ids(self, execute_task):
        task = execute_task('test_queries_via_ids')
        entry = task.entries[0]
        assert entry['tvmaze_series_id'] == 13, 'series id should be 13, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 211206, (
            'episode id should be 211206, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        entry = task.entries[1]
        assert entry['tvmaze_series_id'] == 13, 'series id should be 13, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 187808, (
            'episode id should be 187808, instead its {}'.format(entry['tvmaze_episode_id'])
        )
        entry = task.entries[2]
        assert entry['tvmaze_series_id'] == 13, 'series id should be 13, instead its {}'.format(
            entry['tvmaze_series_id']
        )
        assert entry['tvmaze_episode_id'] == 284974, (
            'episode id should be 284974, instead its {}'.format(entry['tvmaze_episode_id'])
        )

    def test_ep_mixup_error(self, execute_task):
        task = execute_task('test_ep_mixup_error')

        # force episode lookup
        for entry in task.entries:
            entry.get('tvmaze_episode_season')

        with Session() as session:
            episodes = session.query(TVMazeEpisodes).all()
            assert len(episodes) == 2, (
                'should have two episodes in db, one for Flash and one for Arrow'
            )


@pytest.mark.online
class TestTVMazeUnicodeLookup:
    config = """
        templates:
          global:
            tvmaze_lookup: yes
            metainfo_series: yes
        tasks:
          test_unicode:
            disable: seen
            mock:
                - {'title': 'KrØniken 2004 S01E01', 'url': 'mock://whatever'}
            if:
                - tvmaze_series_year > now.year - 1: reject
    """

    def test_unicode(self, execute_task):
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TVMazeLookup).all()
            assert len(r) == 1, 'Should have added a search result'
            assert r[0].search_name == 'kr\xf8niken 2004', 'The search result should be lower case'
        execute_task('test_unicode')
        with Session() as session:
            r = session.query(TVMazeLookup).all()
            assert len(r) == 1, 'Should not have added a new row'


@pytest.mark.online
class TestTVMazeSeasonLookup:
    config = """
        templates:
          global:
            tvmaze_lookup: yes
            metainfo_series: yes
        tasks:
          test_season_pack:
            disable: seen
            mock:
            - title: 'The Flash (2014) S01'
            series:
            - The Flash (2014):
                season_packs: yes
    """

    def test_season_pack_lookup(self, execute_task):
        task = execute_task('test_season_pack')
        entry = task.entries[0]
        assert entry['tvmaze_season_id'] == 40
