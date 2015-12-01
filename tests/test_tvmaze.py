from __future__ import unicode_literals, division, absolute_import

from flexget.manager import Session
from flexget.plugins.api_tvmaze import APITVMaze, TVMazeLookup, TVMazeSeries
from tests import FlexGetBase, use_vcr

lookup_series = APITVMaze.series_lookup


class TestTVMazeShowLookup(FlexGetBase):
    __yaml__ = """
        templates:
          global:
            tvmaze_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{tvdb_id}}{{tvmaze_episode_name}}{{tvmaze_series_name}}"
        tasks:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
            series:
              - House
              - Doctor Who 2005
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
              - {title: 'The.Flash.2014.S02E06.HDTV.x264-LOL'}
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

    """

    @use_vcr
    def test_lookup_name(self):
        """tvmaze: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['tvmaze_series_id'] == 118, \
            'Tvmaze_ID should be 118 is %s for %s' % (entry['tvmaze_series_name'], entry['series_name'])
        assert entry['tvmaze_series_status'] == 'Ended', 'Series Status should be "ENDED" returned %s' \
                                                         % (entry['tvmaze_series_status'])

    @use_vcr
    def test_lookup(self):
        """tvmaze: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['tvmaze_episode_name'] == 'Paternity', \
            '%s tvmaze_episode_name should be Paternity, is actually %s' % (
                entry['title'], entry['tvmaze_episode_name'])
        assert entry['tvmaze_series_status'] == 'Ended', \
            'status for %s is %s, should be "ended"' % (entry['title'], entry['tvmaze_series_status'])
        assert entry[
                   'afield'] == '73255PaternityHouse', 'afield was not set correctly, expected 73255PaternityHouse, got %s' % \
                                                       entry['afield']
        assert self.task.find_entry(tvmaze_episode_name='School Reunion'), \
            'Failed imdb lookup Doctor Who 2005 S02E03'

    @use_vcr
    def test_unknown_series(self):
        # Test an unknown series does not cause any exceptions
        self.execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = self.task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    @use_vcr
    def test_search_results(self):
        self.execute_task('test_search_result')
        entry = self.task.entries[0]
        print entry['tvmaze_series_name'].lower()
        assert entry['tvmaze_series_name'].lower() == 'Shameless'.lower(), 'lookup failed'
        with Session() as session:
            assert self.task.entries[1]['tvmaze_series_name'].lower() == 'Shameless'.lower(), 'second lookup failed'

            assert len(session.query(TVMazeLookup).all()) == 1, 'should have added 1 show to search result'

            assert len(session.query(TVMazeSeries).all()) == 1, 'should only have added one show to show table'
            assert session.query(
                TVMazeSeries).first().name == 'Shameless', 'should have added Shameless and not Shameless (2011)'
            # change the search query
            session.query(TVMazeLookup).update({'search_name': "Shameless.S01E03.HDTV-FlexGet"})
            session.commit()

            lookupargs = {'title': "Shameless.S01E03.HDTV-FlexGet"}
            series = APITVMaze.series_lookup(**lookupargs)

            assert series.tvdb_id == entry['tvdb_id'], 'tvdb id should be the same as the first entry'
            assert series.tvmaze_id == entry['tvmaze_series_id'], 'tvmaze id should be the same as the first entry'
            assert series.name.lower() == entry['tvmaze_series_name'].lower(), 'series name should match first entry'

    @use_vcr()
    def test_date(self):
        self.execute_task('test_date')
        entry = self.task.find_entry(title='the daily show 2012-6-6')
        assert entry.get('tvmaze_series_id') == 249, 'expected tvmaze_series_id 249, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_episode_id') == 20471, 'episode id should be 20471, is actually %s' % entry.get(
            'tvmaze_episode_id')

    @use_vcr
    def test_title_with_year(self):
        self.execute_task('test_title_with_year')
        entry = self.task.find_entry(title='The.Flash.2014.S02E06.HDTV.x264-LOL')
        assert entry.get('tvmaze_series_id') == 13, 'expected tvmaze_series_id 13, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_series_year') == 2014, 'expected tvmaze_series_year 2014, got %s' % entry.get(
            'tvmaze_series_year')

    def test_from_filesystem(self):
        self.execute_task('test_from_filesystem')
        entry = self.task.find_entry(title='Marvels.Jessica.Jones.S01E02.PROPER.720p.WEBRiP.x264-QCF')
        assert entry.get('tvmaze_series_id') == 1370, 'expected tvmaze_series_id 1370, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_episode_id') == 206178, 'episode id should be 206178, is actually %s' % entry.get(
            'tvmaze_episode_id')
        entry = self.task.find_entry(title='Marvels.Jessica.Jones.S01E03.720p.WEBRiP.x264-QCF')
        assert entry.get('tvmaze_series_id') == 1370, 'expected tvmaze_series_id 1370, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_episode_id') == 206177, 'episode id should be 206177, is actually %s' % entry.get(
            'tvmaze_episode_id')
        entry = self.task.find_entry(title='The.Big.Bang.Theory.S09E09.720p.HDTV.X264-DIMENSION')
        assert entry.get('tvmaze_series_id') == 66, 'expected tvmaze_series_id 66, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_episode_id') == 409180, 'episode id should be 409180, is actually %s' % entry.get(
            'tvmaze_episode_id')
        entry = self.task.find_entry(title='The.Flash.S02E04.1080p.WEB-DL.DD5.1.H.264-KiNGS')
        assert entry.get('tvmaze_series_id') == 13, 'expected tvmaze_series_id 13, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_episode_id') == 284974, 'episode id should be 284974, is actually %s' % entry.get(
            'tvmaze_episode_id')
        entry = self.task.find_entry(title='The.Walking.Dead.S06E08.Start.to.Finish-SiCKBEARD')
        assert entry.get('tvmaze_series_id') == 73, 'expected tvmaze_series_id 73, got %s' % entry.get(
            'tvmaze_series_id')
        assert entry.get('tvmaze_episode_id') == 185073, 'episode id should be 185073, is actually %s' % entry.get(
            'tvmaze_episode_id')

