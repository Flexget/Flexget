from tests import FlexGetBase
import os
import os.path

class TestExistsSeries(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'Foo.Bar.S01E02.XViD-FlexGet'}
              - {title: 'Foo.Bar.S01E03.XViD-FlexGet'}
            series:
              - foo bar
            exists_series: test_exists_series/
            
          test_diff_qualities:
            input_mock:
              - {title: 'Asdf.S01E02.720p-FlexGet'}
            series:
              - asdf
            exists_series: test_exists_series/
    """

    test_dirs = ['Foo.Bar.S01E02.XViD.FlexGet', 'Asdf.S01E02.HDTV-FlexGet']
    
    def __init__(self):
        self.test_home = None

    def setup(self):
        FlexGetBase.setUp(self)
        # create test dirs
        self.test_home = os.path.join(self.manager.config_base, 'test_exists_series')
        os.mkdir(self.test_home)
        for dir in self.test_dirs:
            os.mkdir(os.path.join(self.test_home, dir))
        
    def teardown(self):
        # remove test dirs
        for dir in self.test_dirs:
            os.rmdir(os.path.join(self.test_home, dir))
        os.rmdir(self.test_home)
        FlexGetBase.tearDown(self)

    def test_existing(self):
        self.execute_feed('test')
        assert not self.feed.find_entry('accepted', title='Foo.Bar.S01E02.XViD-FlexGet'), \
            'Foo.Bar.S01E02.XViD-FlexGet should not have been accepted (exists)'
        assert self.feed.find_entry('accepted', title='Foo.Bar.S01E03.XViD-FlexGet'), \
            'Foo.Bar.S01E03.XViD-FlexGet should have been accepted'
            
    def test_diff_qualities(self):
        self.execute_feed('test_diff_qualities')
        assert self.feed.find_entry('accepted', title='Asdf.S01E02.720p-FlexGet'), \
            'Asdf.S01E02.720p-FlexGet should have been accepted'
