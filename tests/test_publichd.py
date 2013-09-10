from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr

class TestPublicHD(FlexGetBase):

    __yaml__ = """
        tasks:
          parse:
            publichd: 'https://publichd.se/index.php?page=torrents&category=14'
        
          search:
            discover:
              what:
                - mock:
                  - {title: Braveheart }
                  - {title: Star Wars }
              from:
                - publichd: 'https://publichd.se/index.php?page=torrents&category=2'
              
    """

    @attr(online=True)
    def test_parse(self):
        """publichd: Test parse (ONLINE)"""
        self.execute_task('parse')
        assert len(self.task.entries), 'No entries found'


    @attr(online=True)
    def test_search(self):
        """publichd: Test search (ONLINE)"""
        self.execute_task('search')
        assert len(self.task.entries), 'No entries found'
