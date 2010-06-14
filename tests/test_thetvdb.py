from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestImdb(FlexGetBase):

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
