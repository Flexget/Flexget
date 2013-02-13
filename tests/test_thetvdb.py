from __future__ import unicode_literals, division, absolute_import
from nose.plugins.attrib import attr
from flexget.manager import Session
from flexget.plugins.api_tvdb import lookup_episode
from tests import FlexGetBase


class TestThetvdbLookup(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            thetvdb_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{ tvdb_id }}{{ tvdb_ep_name }}"
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
          test_mark_expired:
            mock:
              - {title: 'House.S02E02.hdtv'}
            metainfo_series: yes
            accept_all: yes
            disable_builtins: [seen]
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

    @attr(online=True)
    def test_lookup(self):
        """thetvdb: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['tvdb_ep_name'] == 'Paternity', \
            '%s tvdb_ep_name should be Paternity' % entry['title']
        assert int(entry['tvdb_runtime']) == 60, \
            'runtime for %s is %s, should be 60' % (entry['title'], entry['tvdb_runtime'])
        assert entry['tvdb_genres'] == ['Comedy', 'Drama']
        assert entry['afield'] == '73255Paternity', 'afield was not set correctly'
        assert self.task.find_entry(tvdb_ep_name='School Reunion'), \
            'Failed imdb lookup Doctor Who 2005 S02E03'

    @attr(online=True)
    def test_unknown_series(self):
        # Test an unknown series does not cause any exceptions
        self.execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = self.task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    @attr(online=True)
    def test_mark_expired(self):

        def test_run():
            # Run the task and check tvdb data was populated.
            self.execute_task('test_mark_expired')
            entry = self.task.find_entry(title='House.S02E02.hdtv')
            assert entry['tvdb_ep_name'] == 'Autopsy'

        # Run the task once, this populates data from tvdb
        test_run()
        # Run the task again, this should load the data from cache
        test_run()
        # Manually mark the data as expired, to test cache update
        session = Session()
        ep = lookup_episode(name='House', seasonnum=2, episodenum=2, session=session)
        ep.expired = True
        ep.series.expired = True
        session.commit()
        session.close()
        test_run()

    @attr(online=True)
    def test_date(self):
        self.execute_task('test_date')
        entry = self.task.find_entry(title='the daily show 2012-6-6')
        assert entry
        assert entry['tvdb_ep_name'] == 'Michael Fassbender'

    @attr(online=True)
    def test_absolute(self):
        self.execute_task('test_absolute')
        entry = self.task.find_entry(title='naruto 128')
        assert entry
        assert entry['tvdb_ep_name'] == 'A Cry on Deaf Ears'


class TestThetvdbFavorites(FlexGetBase):
    """
        Tests thetvdb favorites plugin with a test user at thetvdb.
        Test user info:
        username: flexget
        password: flexget
        Account ID: 80FB8BD0720CA5EC
        Favorites: House, Doctor Who 2005, Penn & Teller: Bullshit, Hawaii Five-0 (2010)
    """

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
              - {title: 'Lost.S03E02.720p-FlexGet'}
              - {title: 'Penn.and.Teller.Bullshit.S02E02.720p.x264'}
            import_series:
              from:
                thetvdb_favorites:
                  account_id: 80FB8BD0720CA5EC
          test_strip_dates:
            thetvdb_favorites:
              account_id: 80FB8BD0720CA5EC
              strip_dates: yes
    """

    @attr(online=True)
    def test_favorites(self):
        """thetvdb: Test favorites (ONLINE)"""
        self.execute_task('test')
        assert self.task.find_entry('accepted', title='House.S01E02.HDTV.XViD-FlexGet'), \
            'series House should have been accepted'
        assert self.task.find_entry('accepted', title='Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'), \
            'series Doctor Who 2005 should have been accepted'
        assert self.task.find_entry('accepted', title='Penn.and.Teller.Bullshit.S02E02.720p.x264'), \
            'series Penn and Teller Bullshit should have been accepted'
        entry = self.task.find_entry(title='Lost.S03E02.720p-FlexGet')
        assert entry, 'Entry not found?'
        assert entry not in self.task.accepted, \
            'series Lost should not have been accepted'

    @attr(online=True)
    def test_strip_date(self):
        self.execute_task('test_strip_dates')
        assert self.task.find_entry(title='Hawaii Five-0'), \
            'series Hawaii Five-0 (2010) should have date stripped'
