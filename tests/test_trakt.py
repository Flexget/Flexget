from __future__ import unicode_literals, division, absolute_import
from nose.plugins.attrib import attr
from flexget.manager import Session
from flexget.plugins.api_trakt import ApiTrakt
lookup_series = ApiTrakt.lookup_series
lookup_episode = ApiTrakt.lookup_episode
from tests import FlexGetBase


class TestTraktLookup(FlexGetBase):

    __yaml__ = """
        templates:
          global:
            trakt_lookup: yes
            # Access a tvdb field to cause lazy loading to occur
            set:
              afield: "{{trakt_series_tvdb_id}}{{trakt_ep_name}}"
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
          test_absolute:
            mock:
              - title: naruto 128
            series:
              - naruto

    """

    @attr(online=True)
    def test_lookup(self):
        """trakt: Test Lookup (ONLINE)"""
        self.execute_task('test')
        entry = self.task.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['trakt_ep_name'] == 'Paternity', \
            '%s trakt_ep_name should be Paternity' % entry['title']
        assert entry['trakt_series_status'] == 'Ended', \
            'runtime for %s is %s, should be Ended' % (entry['title'], entry['trakt_series_status'])
        assert entry['afield'] == '73255Paternity', 'afield was not set correctly'
        assert self.task.find_entry(trakt_ep_name='School Reunion'), \
            'Failed imdb lookup Doctor Who 2005 S02E03'

    @attr(online=True)
    def test_unknown_series(self):
        # Test an unknown series does not cause any exceptions
        self.execute_task('test_unknown_series')
        # Make sure it didn't make a false match
        entry = self.task.find_entry('accepted', title='Aoeu.Htns.S01E01.htvd')
        assert entry.get('tvdb_id') is None, 'should not have populated tvdb data'

    @attr(online=True)
    def test_date(self):
        self.execute_task('test_date')
        entry = self.task.find_entry(title='the daily show 2012-6-6')
        assert entry.get('tvdb_id') is None, 'should not have populated trakt data'

    @attr(online=True)
    def test_absolute(self):
        self.execute_task('test_absolute')
        entry = self.task.find_entry(title='naruto 128')
        assert entry.get('tvdb_id') is None, 'should not have populated trakt data'
