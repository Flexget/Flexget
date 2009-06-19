#!/usr/bin/python

import os, sys
from nose.tools import *
from nose.plugins.attrib import attr
from flexget.manager import Manager, Session
from flexget.plugin import get_plugin_by_name, load_plugins
from flexget.options import OptionParser
from flexget.feed import Feed
from flexget import initialize_logging
import yaml

test_options = None

plugins_loaded = False
def setup_once():
    global plugins_loaded, test_options
    if not plugins_loaded:
        initialize_logging(True)
        parser = OptionParser(True)
        load_plugins(parser)
        test_options = parser.parse_args()[0]
        plugins_loaded = True

class MockManager(Manager):
    unit_test = True
    def __init__(self, config_text, config_name):
        self.config_text = config_text
        self.configname = config_name
        Manager.__init__(self, test_options, os.path.dirname(os.path.abspath(sys.path[0])))

    def load_config(self):
        try:
            self.config = yaml.safe_load(self.config_text)
        except Exception, e:
            log.critical(e)
            print ''
            print '-'*79
            print ' This is caused by malformed configuration file, common reasons:'
            print '-'*79
            print ''
            print ' o Indentation error'
            print ' o Missing : from end of the line'
            print ' o If text contains : it must be quoted\n'
            area = str(e.context_mark)[str(e.context_mark).find('line'):]
            print ' Check your configuration near %s' % area
            print ' Fault is almost always in this line or previous\n'
            sys.exit(1)

class FlexGetBase(object):
    __yaml__ = """Yaml goes here"""

    def setUp(self):
        """Set up test env"""
        setup_once()
        self.manager = MockManager(self.__yaml__, self.__class__.__name__)

    def tearDown(self):
        try:
            self.feed.session.close()
        except:
            pass
        if os.path.exists(self.manager.db_filename):
            os.remove(self.manager.db_filename)

    def execute_feed(self, name):
        """Use to execute one test feed from config"""
        config = self.manager.config['feeds'][name]
        if hasattr(self, 'feed'):
            if hasattr(self, 'session'):
                self.feed.session.close() # pylint: disable-msg=E0203
        self.feed = Feed(self.manager, name, config)
        self.feed.session = Session()
        self.feed.process_start()
        self.feed.execute()
        self.feed.process_end()
        
    def get_plugin(self, event, keyword):
        plugin = get_plugin_by_name(keyword)
        if not plugin:
            raise Exception('plugin %s isn\'t loaded (event %s)' % (keyword, event))
        return plugin

    def dump(self):
        """Helper method for debugging"""
        print 'entries=%s' % self.feed.entries
        print 'accepted=%s' % self.feed.accepted
        print 'rejected=%s' % self.feed.rejected


class TestRegexp(FlexGetBase):
    __yaml__ = """
        global:
          input_mock:
            - {title: 'regexp1', url: 'http://localhost/regexp/1', 'imdb_score': 5}
            - {title: 'regexp2', url: 'http://localhost/regexp/2', 'bool_attr': true}
            - {title: 'regexp3', url: 'http://localhost/regexp/3', 'imdb_score': 5}
            - {title: 'regexp4', url: 'http://localhost/regexp/4', 'imdb_score': 5}
            - {title: 'regexp5', url: 'http://localhost/regexp/5', 'imdb_score': 5}
            - {title: 'regexp6', url: 'http://localhost/regexp/6', 'imdb_score': 5}
            - {title: 'regexp7', url: 'http://localhost/regexp/7', 'imdb_score': 5}
            - {title: 'regexp8', url: 'http://localhost/regexp/8', 'imdb_score': 5}
            - {title: 'regexp9', url: 'http://localhost/regexp/9', 'imdb_score': 5}
          seen: false


        feeds:
          # test accepting, setting custom path (both ways), test not (secondary regexp)
          test_accept:
            regexp:
              accept:
                - regexp1
                - regexp2: ~/custom_path/2/
                - regexp3:
                    path: ~/custom_path/3/
                - regexp4:
                    not:
                      - exp4
                      
          # test rejecting        
          test_reject:
            regexp:
              reject:
                - regexp1
                
          # test rest
          test_rest:
            regexp:
              accept:
                - regexp1
              rest: reject
              
              
          # test excluding
          test_excluding:
            regexp:
              accept_excluding:
                - regexp1
                
          # test from
          test_from:
            regexp:
              accept:
                - localhost:
                    from:
                      - title
    """
    def testAccept(self):
        self.execute_feed('test_accept')
        assert self.feed.find_entry('accepted', title='regexp1'), 'regexp1 should have been accepted'
        assert self.feed.find_entry('accepted', title='regexp2'), 'regexp2 should have been accepted'
        assert self.feed.find_entry('accepted', title='regexp3'), 'regexp3 should have been accepted'
        assert self.feed.find_entry('entries', title='regexp4'), 'regexp4 should have been left'
        assert self.feed.find_entry('accepted', title='regexp2', path='~/custom_path/2/'), 'regexp2 should have been accepter with custom path'
        assert self.feed.find_entry('accepted', title='regexp3', path='~/custom_path/3/'), 'regexp3 should have been accepter with custom path'
            
    def testReject(self):
        self.execute_feed('test_reject')
        assert self.feed.find_entry('rejected', title='regexp1'), 'regexp1 should have been rejected'

    def testRest(self):
        self.execute_feed('test_rest')
        assert self.feed.find_entry('accepted', title='regexp1'), 'regexp1 should have been accepted'
        assert self.feed.find_entry('rejected', title='regexp3'), 'regexp3 should have been rejected'
            
    def testExcluding(self):
        self.execute_feed('test_excluding')
        assert not self.feed.find_entry('accepted', title='regexp1'), 'regexp1 should not have been accepted'
        assert self.feed.find_entry('accepted', title='regexp2'), 'regexp2 should have been accepted'
        assert self.feed.find_entry('accepted', title='regexp3'), 'regexp3 should have been accepted'

    def testFrom(self):
        self.execute_feed('test_from')
        assert not self.feed.accepted, 'should not have accepted anything'
        
class TestResolvers(FlexGetBase):
    """
        Bad example, does things manually, you should use feed.find_entry to check existance
    """
    __yaml__ = """
        feeds:
          test:
            # make test data
            input_mock:
              - {title: 'something', url: 'http://thepiratebay.org/tor/8492471/Test.avi'}
              - {title: 'bar', url: 'http://thepiratebay.org/search/something'}
              - {title: 'nyaa', url: 'http://www.nyaatorrents.org/?page=torrentinfo&tid=12345'}
    """
    def setUp(self):
        FlexGetBase.setUp(self)
        self.execute_feed('test')
        
    def get_resolver(self, name):
        info = get_plugin_by_name(name)
        return info.instance
        
    def testPirateBay(self):
        # test with piratebay entry
        resolver = self.get_resolver('piratebay')
        entry = self.feed.entries[0]
        assert_true(resolver.resolvable(self.feed, entry))

    def testPirateBaySearch(self):
        # test with piratebay entry
        resolver = self.get_resolver('piratebay')
        entry = self.feed.entries[1]
        assert_true(resolver.resolvable(self.feed, entry))
        
    def testNyaaTorrents(self):
        entry = self.feed.entries[2]
        resolver = self.get_resolver('nyaatorrents')
        assert entry['url'] == 'http://www.nyaatorrents.org/?page=torrentinfo&tid=12345'
        assert_true(resolver.resolvable(self.feed, entry))
        resolver.resolve(self.feed, entry)
        assert entry['url'] == 'http://www.nyaatorrents.org/?page=download&tid=12345'


class TestDisableBuiltins(FlexGetBase):
    """
        Quick hack, test disable functionality by checking if seen filtering (builtin) is working
    """
    __yaml__ = """
        feeds:
            test:
                input_mock:
                    - {title: 'dupe1', url: 'http://localhost/dupe', 'imdb_score': 5}
                    - {title: 'dupe2', url: 'http://localhost/dupe', 'imdb_score': 5}
                disable_builtins: true 

            test2:
                input_mock:
                    - {title: 'dupe1', url: 'http://localhost/dupe', 'imdb_score': 5, description: 'http://www.imdb.com/title/tt0409459/'}
                    - {title: 'dupe2', url: 'http://localhost/dupe', 'imdb_score': 5}
                disable_builtins:
                    - seen
                    - cli_config
    """
    def testDisableBuiltins(self):
        self.execute_feed('test')
        assert self.feed.find_entry(title='dupe1') and self.feed.find_entry(title='dupe2'), 'disable_builtins is not working?'

#class TestManager(FlexGetBase):
#    def setUp(self):
#        # just load with some conf
#        self.config = 'regexp.yml'
#        FlexGetBase.setUp(self, os.path.dirname(__file__))
#        
#    def testFailed(self):
#        pass
#        """
#        e = Entry()
#        e['title'] = 'test'
#        e['url'] = 'http://localhost/mock'
#        self.manager.add_failed(e)
#        assert len(self.manager.shelve_session['failed']) == 1, 'failed to add'
#        e = Entry()
#        e['title'] = 'test 2'
#        e['url'] = 'http://localhost/mock'
#        self.manager.add_failed(e)
#        assert len(self.manager.shelve_session['failed']) == 2, 'failed to add again'
#        self.manager.add_failed(e)
#        assert len(self.manager.shelve_session['failed']) == 2, 'failed to filter already added'
#        """
        
class TestInputHtml(FlexGetBase):
    __yaml__ = """
        feeds:
          test:
            html: http://download.flexget.com/
    """
    def testParsing(self):
        self.execute_feed('test')
        assert self.feed.entries, 'did not produce entries'

class TestRlsLog(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            rlslog: http://www.rlslog.net/category/movies/dvdrip/
    """

    def testParsing(self):
        self.execute_feed('test')
        assert self.feed.entries, 'no entries created'
        
        
class TestDownload(FlexGetBase):
    __yaml__ = """
        feeds:
          test:
            # make test data
            input_mock:
              - {title: 'README', url: 'http://svn.flexget.com/trunk/bootstrap.py', 'filename': 'flexget_test/data'}
            accept_all: true
            download: ~/
    """
    def tearDown(self):
        FlexGetBase.tearDown(self)
        if hasattr(self, 'testfile') and os.path.exists(self.testfile):
            os.remove(self.testfile)
        temp_dir = os.path.join(self.manager.config_base, 'temp')
        if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
            os.rmdir(temp_dir)

    @attr(online=True)
    def testDownload(self):
        self.testfile = os.path.expanduser('~/flexget_test_data')
        if os.path.exists(self.testfile):
            os.remove(self.testfile)
        # executes feed and downloads the file
        self.execute_feed('test')
        assert os.path.exists(self.testfile), 'download file does not exists'
