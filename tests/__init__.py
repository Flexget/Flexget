#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import os
import sys
import flexget.logger
from flexget.manager import Manager
from flexget.plugin import load_plugins
from flexget.options import CoreArgumentParser
from flexget.task import Task
from tests import util
import yaml
import logging

log = logging.getLogger('tests')

test_arguments = None
plugins_loaded = False


def setup_logging_level():
    # set logging level according to nosetests verbosity;
    # overrides the default level in tests/logging.cfg
    level = logging.DEBUG
    if "--verbose" in sys.argv or "-v" in sys.argv:
        level = flexget.logger.TRACE
    elif "--quiet" in sys.argv or "-q" in sys.argv:
        level = logging.INFO

    logging.getLogger().setLevel(level)
    return level


def setup_once():
    global plugins_loaded, test_arguments
    if not plugins_loaded:
        flexget.logger.initialize(True)
        setup_logging_level()
        parser = CoreArgumentParser(True)
        load_plugins(parser)
        # store options for MockManager
        test_arguments = parser.parse_args()
        plugins_loaded = True


class MockManager(Manager):
    unit_test = True

    def __init__(self, config_text, config_name, db_uri=None):
        self.config_text = config_text
        self._db_uri = db_uri or 'sqlite:///:memory:'
        super(MockManager, self).__init__(test_arguments)
        self.config_name = config_name

    def initialize(self):
        self.database_uri = self._db_uri
        log.debug('database_uri: %s' % self.database_uri)
        super(MockManager, self).initialize()

    def find_config(self):
        """
        Override configuration loading
        """
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

    # Set this to True to get a UNIQUE tmpdir; the tmpdir is created on
    # setup as "./tmp/<testname>" and automatically removed on teardown.
    #
    # The instance variable __tmp__ is set to the absolute name of the tmpdir
    # (ending with "os.sep"), and any occurrence of "__tmp__" in __yaml__ or
    # a @with_filecopy destination is also replaced with it.

    # TODO: there's probably flaw in this as this is shared across FlexGetBases ?
    __tmp__ = False

    def __init__(self):
        self.log = log
        self.manager = None
        self.task = None
        self.database_uri = None
        self.base_path = os.path.dirname(__file__)

    def setup(self):
        """Set up test env"""
        setup_once()
        if self.__tmp__:
            self.__tmp__ = util.maketemp() + '/'
            self.__yaml__ = self.__yaml__.replace("__tmp__", self.__tmp__)
        self.manager = MockManager(self.__yaml__, self.__class__.__name__, db_uri=self.database_uri)

    def teardown(self):
        try:
            try:
                self.task.session.close()
            except:
                pass
            self.manager.shutdown()
            self.manager.__del__()
        finally:
            if self.__tmp__:
                import shutil
                log.trace('Removing tmpdir %r' % self.__tmp__)
                shutil.rmtree(self.__tmp__.rstrip(os.sep))

    def execute_task(self, name, abort_ok=False):
        """Use to execute one test task from config"""
        log.info('********** Running task: %s ********** ' % name)
        config = self.manager.config['tasks'][name]
        if hasattr(self, 'task'):
            if hasattr(self, 'session'):
                self.task.session.close() # pylint: disable-msg=E0203
        self.task = Task(self.manager, name, config)
        self.manager.execute(tasks=[self.task])
        if not abort_ok:
            assert not self.task.aborted, 'Task should not have aborted.'

    def dump(self):
        """Helper method for debugging"""
        from flexget.plugins.output.dump import dump
        #from flexget.utils.tools import sanitize
        # entries = sanitize(self.task.entries)
        # accepted = sanitize(self.task.accepted)
        # rejected = sanitize(self.task.rejected)
        print '\n-- ENTRIES: -----------------------------------------------------'
        # print yaml.safe_dump(entries)
        dump(self.task.entries, True)
        print '-- ACCEPTED: ----------------------------------------------------'
        # print yaml.safe_dump(accepted)
        dump(self.task.entries, True)
        print '-- REJECTED: ----------------------------------------------------'
        # print yaml.safe_dump(rejected)
        dump(self.task.entries, True)


class with_filecopy(object):
    """
        @with_filecopy decorator
        make a copy of src to dst for test case and deleted file afterwards

        src can be also be a glob pattern, or a list of patterns; in both
        cases, dst is then handled as a prefix (preferably a temp dir)
    """

    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def __call__(self, func):

        def wrapper(*args, **kwargs):
            import shutil
            import glob

            dst = self.dst
            if "__tmp__" in dst:
                dst = dst.replace('__tmp__', 'tmp/%s/' % util.find_test_name().replace(':', '_'))

            src = self.src
            if isinstance(src, basestring):
                src = [self.src]
            files = []
            for pattern in src:
                files.extend(glob.glob(pattern))

            if len(src) > 1 or set(files) != set(src):
                # Glob expansion, "dst" is a prefix
                pairs = [(i, dst + i) for i in files]
            else:
                # Explicit source and destination names
                pairs = [(self.src, dst)]

            for src, dst in pairs:
                log.trace("Copying %r to %r" % (src, dst))
                shutil.copy(src, dst)
            try:
                return func(*args, **kwargs)
            finally:
                for _, dst in pairs:
                    if os.path.exists(dst):
                        log.trace("Removing %r" % dst)
                        os.remove(dst)

        from nose.tools import make_decorator
        wrapper = make_decorator(func)(wrapper)
        return wrapper
