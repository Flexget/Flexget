from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestThetvdbLookup(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
            series:
              - House
              - Doctor Who 2005
            thetvdb_lookup: yes
    """

    @attr(online=True)
    def test_lookup(self):
        """thetvdb: Test Lookup (ONLINE)"""
        self.execute_feed('test')
        entry = self.feed.find_entry(title='House.S01E02.HDTV.XViD-FlexGet')
        assert entry['ep_name'] == 'Paternity', \
            '%s ep_name should be Paternity' % entry['title']
        assert int(entry['series_runtime']) == 60, \
            'runtime for %s is %s, should be 60' % (entry['title'], entry['series_runtime'])
        assert self.feed.find_entry(ep_name='School Reunion'), \
            'Failed imdb lookup Doctor Who 2005 S02E03'


class TestThetvdbFavorites(FlexGetBase):
    """
        Tests thetvdb favorites plugin with a test user at thetvdb.
        Test user info:
        username: flexget
        password: flexget
        Account ID: 80FB8BD0720CA5EC
        Favorites: House, Doctor Who 2005
    """

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'House.S01E02.HDTV.XViD-FlexGet'}
              - {title: 'Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'}
              - {title: 'Lost.S03E02.720p-FlexGet'}
            thetvdb_favorites:
              account_id: 80FB8BD0720CA5EC
    """

    @attr(online=True)
    def test_favorites(self):
        """thetvdb: Test favorites (ONLINE)"""
        self.execute_feed('test')
        assert self.feed.find_entry('accepted', title='House.S01E02.HDTV.XViD-FlexGet'), \
            'series House should have been accepted'
        assert self.feed.find_entry('accepted', title='Doctor.Who.2005.S02E03.PDTV.XViD-FlexGet'), \
            'series Doctor Who 2005 should have been accepted'
        entry = self.feed.find_entry(title='Lost.S03E02.720p-FlexGet')
        assert entry, 'Entry not found?'
        assert entry not in self.feed.accepted, \
            'series Lost should not have been accepted'
