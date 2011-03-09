#!/usr/bin/python

import os
import sys
import flexget.logger
from flexget.manager import Manager
from flexget.plugin import load_plugins
from flexget.options import CoreOptionParser
from flexget.feed import Feed
import yaml
import logging

log = logging.getLogger('tests')

test_options = None
plugins_loaded = False


def setup_once():
    global plugins_loaded, test_options
    if not plugins_loaded:
        flexget.logger.initialize(True)
        parser = CoreOptionParser(True)
        load_plugins(parser)
        # store options for MockManager
        test_options = parser.parse_args()[0]
        plugins_loaded = True


class MockManager(Manager):
    unit_test = True

    def __init__(self, config_text, config_name):
        self.config_text = config_text
        self.config_name = config_name
        self.config = None
        self.config_base = None
        Manager.__init__(self, test_options)

    def find_config(self):
        try:
            self.config = yaml.safe_load(self.config_text)
            self.config_base = os.path.dirname(os.path.abspath(sys.path[0]))
        except Exception:
            print 'Invalid configuration'
            raise

    # no lock files with unit testing
    def acquire_lock(self):
        pass

    def release_lock(self):
        pass


class FlexGetBase(object):
    __yaml__ = """# Yaml goes here"""

    def __init__(self):
        self.manager = None
        self.feed = None

    def setup(self):
        """Set up test env"""
        setup_once()
        self.manager = MockManager(self.__yaml__, self.__class__.__name__)

    def teardown(self):
        try:
            self.feed.session.close()
        except:
            pass
        self.manager.__del__()

    def execute_feed(self, name):
        """Use to execute one test feed from config"""
        log.info('********** Running feed: %s ********** ' % name)
        config = self.manager.config['feeds'][name]
        if hasattr(self, 'feed'):
            if hasattr(self, 'session'):
                self.feed.session.close() # pylint: disable-msg=E0203
        self.feed = Feed(self.manager, name, config)
        self.manager.execute(feeds=[self.feed])

    def dump(self):
        """Helper method for debugging"""
        from flexget.plugins.output_dump import dump
        #from flexget.utils.tools import sanitize
        # entries = sanitize(self.feed.entries)
        # accepted = sanitize(self.feed.accepted)
        # rejected = sanitize(self.feed.rejected)
        print '\n-- ENTRIES: -----------------------------------------------------'
        # print yaml.safe_dump(entries)
        dump(self.feed.entries, True)
        print '-- ACCEPTED: ----------------------------------------------------'
        # print yaml.safe_dump(accepted)
        dump(self.feed.entries, True)
        print '-- REJECTED: ----------------------------------------------------'
        # print yaml.safe_dump(rejected)
        dump(self.feed.entries, True)


class with_filecopy(object):
    """
        @with_filecopy decorator
        make a copy of src to dst for test case and deleted file afterwards
    """

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def __call__(self, func):

        def wrapper(*args, **kwargs):
            import shutil
            import glob
            import os
            
            files = glob.glob(self.src)
            if files[0] != self.src:
                # Glob expansion, "dst" is a prefix
                pairs = [(i, self.dst + i) for i in files]
            else:
                # Explicit source and destination names
                pairs = [(self.src, self.dst)]
   
            for src, dst in pairs:
                log.debugall("Copying %r to %r (in %r)" % (src, dst, os.getcwd()))
                shutil.copy(src, dst)
            try:
                return func(*args, **kwargs)
            finally:
                for _, dst in pairs:             
                    if os.path.exists(dst):
                        log.debugall("Removing %r" % dst)            
                        os.remove(dst)

        from nose.tools import make_decorator
        wrapper = make_decorator(func)(wrapper)
        return wrapper
