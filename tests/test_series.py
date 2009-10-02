from tests import FlexGetBase
from nose.tools import assert_raises, assert_true
from flexget.utils.series import SeriesParser, ParseWarning
import os

class TestFilterSeries(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            # test data
            input_mock:
              - {title: 'Some.Series.S01E20.720p.XViD-FlexGet', url: 'http://localhost/irrelevant1'}
              - {title: 'Another.Series.S01E20.720p.XViD-FlexGet', url: 'http://localhost/irrelevant2'}
              - {title: 'Another.Series.S01E10.720p.XViD-FlexGet', url: 'http://localhost/irrelevant3'}
              - {title: 'Another.Series.S01E16.720p.XViD-FlexGet', url: 'http://localhost/irrelevant4'}
              - {title: 'Date.Series.10-11-2008.XViD', url: 'http://localhost/irrelevant5'}
              - {title: 'Date.Series.10.12.2008.XViD', url: 'http://localhost/irrelevant6'}
              - {title: 'Date.Series.2008-10-13.XViD', url: 'http://localhost/irrelevant7'}
              - {title: 'Date.Series.2008x10.14.XViD', url: 'http://localhost/irrelevant8'}
              - {title: 'Useless title', url: 'http://localhost/irrelevant9', filename: 'Filename.Series.S01E26.XViD'}
              - {title: 'Empty.Description.S01E22.XViD', url: 'http://localhost/irrelevant10', description: ''}
              
            series:
              - some series:
                  quality: 1080p
                  timeframe: 4 hours
              - another series
              - date series
              - filename series
              - empty description
    """
    
    def setUp(self):
        FlexGetBase.setUp(self)
        self.execute_feed('test')

    def testSeries(self):
        # TODO: needs to be fixed after series is converted into SQLAlchemy
        # 'some series' should be in timeframe-queue
        #self.feed.shared_cache.set_namespace('series')
        #s = self.feed.shared_cache.get('some series')
        #assert isinstance(s, dict)
        #assert not s.get('S1E20', {}).get('info').get('downloaded')
        
        # normal passing
        assert self.feed.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'), 'Another.Series.S01E20.720p.XViD-FlexGet should have passed'

        # date formats
        df = ['Date.Series.10-11-2008.XViD','Date.Series.10.12.2008.XViD', 'Date.Series.2008-10-13.XViD', 'Date.Series.2008x10.14.XViD']
        for d in df:
            assert self.feed.find_entry(title=d), 'Date format did not match %s' % d
        
        # parse from filename
        assert self.feed.find_entry(filename='Filename.Series.S01E26.XViD'), 'Filename parsing failed'
        
        # empty description
        assert self.feed.find_entry(title='Empty.Description.S01E22.XViD'), 'Empty Description failed'
        
    def testAdvancement(self):
        return
        
        # TODO: FIX FIX AND ENABLE
        
        # episode advancement
        assert not self.feed.find_entry('rejected', title='Another.Series.S01E10.720p.XViD-FlexGet'), 'Another.Series.S01E10.720p.XViD-FlexGet should NOT have passed because of episode advancement'
        assert self.feed.find_entry('accepted', title='Another.Series.S01E16.720p.XViD-FlexGet'), 'Another.Series.S01E16.720p.XViD-FlexGet should have passed because of episode advancement grace magin'
        

class TestSeriesParser(object):

    def testParser(self):
        
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 'Something.Interesting.S01E02.Proper-FlexGet'
        s.parse()
        assert s.season == 1
        assert s.episode == 2
        assert s.quality == 'unknown'
        assert not s.proper_or_repack, 'did not detect proper'

        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 'The.Something.Interesting.S01E02-FlexGet'
        s.parse()
        assert not s.valid, 'Should not be valid'

        s = SeriesParser()
        s.name = '25'
        s.data = '25.And.More.S01E02-FlexGet'
        s.parse()
        # TODO: This behavior should be changed. uhh, why?
        assert s.valid, 'Fix the implementation, should not be valid'

        # test invalid name
        s = SeriesParser()
        s.name = 1
        s.data = 'Something'
        assert_raises(Exception, s.parse)

        # test confusing format
        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something.2008x12.13-FlexGet'
        s.parse()
        assert not s.episode, 'Should not have episode'
        assert not s.season, 'Should not have season'
        assert s.id == '2008-12-13', 'invalid id'
        assert s.valid, 'should not valid'
        
        # test 01x02 format
        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something.01x02-FlexGet'
        s.parse()
        assert (s.season==1 and s.episode==2), 'failed to parse 01x02'

        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something 1 x 2-FlexGet'
        s.parse()
        assert (s.season==1 and s.episode==2), 'failed to parse 1 x 2'
        
        # test invalid data
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 1
        assert_raises(Exception, s.parse)

    def testSeasonPacks(self):
        
        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something S02 Pack 720p WEB-DL-FlexGet'
        assert_raises(ParseWarning, s.parse)
