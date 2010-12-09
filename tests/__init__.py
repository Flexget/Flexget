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

    def load_config(self):
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

    def execute_feed(self, name):
        """Use to execute one test feed from config"""
        log.info('********** Running feed: %s ********** ' % name)
        config = self.manager.config['feeds'][name]
        if hasattr(self, 'feed'):
            if hasattr(self, 'session'):
                self.feed.session.close() # pylint: disable-msg=E0203
        self.feed = Feed(self.manager, name, config)
        # self.feed.session = Session()
        self.feed.process_start()
        if self.feed.enabled:
            self.feed.execute()
        else:
            log.debug('Feed \'%s\' has been disabled, not running' % self.feed.name)
        self.feed.process_end()
        # self.feed.session.commit()

    def dump(self):
        """Helper method for debugging"""
        from flexget.utils.tools import sanitize
        # entries = sanitize(self.feed.entries)
        # accepted = sanitize(self.feed.accepted)
        # rejected = sanitize(self.feed.rejected)
        print '-- ENTRIES: -----------------------------------------------------'
        # print yaml.safe_dump(entries)
        print self.feed.entries
        print '-- ACCEPTED: ----------------------------------------------------'
        # print yaml.safe_dump(accepted)
        print self.feed.accepted
        print '-- REJECTED: ----------------------------------------------------'
        # print yaml.safe_dump(rejected)
        print self.feed.rejected


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
            import os
            shutil.copy(self.src, self.dst)
            try:
                return func(*args, **kwargs)
            finally:
                os.remove(self.dst)

        from nose.tools import make_decorator
        wrapper = make_decorator(func)(wrapper)
        return wrapper
