#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import inspect
import os
import sys
import yaml
import logging
import warnings
from contextlib import contextmanager
from functools import wraps

import mock
from nose.plugins.attrib import attr
from vcr import VCR

import flexget.logger
from flexget.manager import Manager
from flexget.plugin import load_plugins
from flexget.options import get_parser
from flexget.task import Task, TaskAbort
from tests import util

log = logging.getLogger('tests')

VCR_CASSETTE_DIR = os.path.join(os.path.dirname(__file__), 'cassettes')
VCR_RECORD_MODE = os.environ.get('VCR_RECORD_MODE', 'once')

vcr = VCR(cassette_library_dir=VCR_CASSETTE_DIR, record_mode=VCR_RECORD_MODE)
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
        warnings.simplefilter('error')
        # VCR.py mocked functions not handle ssl verification well. Older versions of urllib3 don't have this
        if VCR_RECORD_MODE != 'off':
            try:
                from requests.packages.urllib3.exceptions import SecurityWarning
                warnings.simplefilter('ignore', SecurityWarning)
            except ImportError:
                pass
        load_plugins()
        # store options for MockManager
        test_arguments = get_parser().parse_args(['execute'])
        plugins_loaded = True


def use_vcr(func):
    """
    Decorator for test functions which go online. A vcr cassette will automatically be created and used to capture and
    play back online interactions. The nose 'vcr' attribute will be set, and the nose 'online' attribute will be set on
    it based on whether it might go online.

    The record mode of VCR can be set using the VCR_RECORD_MODE environment variable when running tests. Depending on
    the record mode, and the existence of an already recorded cassette, this decorator will also dynamically set the
    nose 'online' attribute.
    """
    module = func.__module__.split('tests.')[-1]
    class_name = inspect.stack()[1][3]
    cassette_name = '.'.join([module, class_name, func.__name__])
    cassette_path, _ = vcr.get_path_and_merged_config(cassette_name)
    online = True
    # Set our nose online attribute based on the VCR record mode
    if vcr.record_mode == 'none':
        online = False
    elif vcr.record_mode == 'once':
        online = not os.path.exists(cassette_path)
    func = attr(online=online, vcr=True)(func)
    # If we are not going online, disable domain delay during test
    if not online:
        func = mock.patch('flexget.utils.requests.wait_for_domain', new=mock.MagicMock())(func)
    # VCR playback on windows needs a bit of help https://github.com/kevin1024/vcrpy/issues/116
    if sys.platform.startswith('win') and vcr.record_mode != 'all' and os.path.exists(cassette_path):
        func = mock.patch('requests.packages.urllib3.connectionpool.is_connection_dropped',
                          new=mock.MagicMock(return_value=False))(func)
    @wraps(func)
    def func_with_cassette(*args, **kwargs):
        with vcr.use_cassette(cassette_name) as cassette:
            try:
                func(*args, cassette=cassette, **kwargs)
            except TypeError:
                func(*args, **kwargs)

    if VCR_RECORD_MODE == 'off':
        return func
    else:
        return func_with_cassette


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

    def find_config(self, *args, **kwargs):
        """
        Override configuration loading
        """
        try:
            self.config = yaml.safe_load(self.config_text) or {}
            self.config_base = os.path.dirname(os.path.abspath(sys.path[0]))
        except Exception:
            print 'Invalid configuration'
            raise

    def load_config(self):
        pass

    def validate_config(self):
        # We don't actually quit on errors in the unit tests, as the configs get modified after manager start
        errors = super(MockManager, self).validate_config()
        for error in errors:
            log.critical(error)

    # no lock files with unit testing
    @contextmanager
    def acquire_lock(self, **kwargs):
        self._has_lock = True
        yield

    def release_lock(self):
        pass


def build_parser_function(parser_name):
    def parser_function(task_name, task_definition):
        task_definition['parsing'] = {'series': parser_name, 'movie': parser_name}
    return parser_function


class FlexGetBase(object):
    __yaml__ = """# Yaml goes here"""

    # Set this to True to get a UNIQUE tmpdir; the tmpdir is created on
    # setup as "./tmp/<testname>" and automatically removed on teardown.
    #
    # The instance variable __tmp__ is set to the absolute name of the tmpdir
    # (ending with "os.sep"), and any occurrence of "__tmp__" in __yaml__ or
    # a @with_filecopy destination is also replaced with it.

    __tmp__ = False

    def __init__(self):
        self.log = log
        self.manager = None
        self.task = None
        self.database_uri = None
        self.base_path = os.path.dirname(__file__)
        self.config_functions = []
        self.tasks_functions = []

    def add_config_function(self, config_function):
        self.config_functions.append(config_function)

    def add_tasks_function(self, tasks_function):
        self.tasks_functions.append(tasks_function)

    def setup(self):
        """Set up test env"""
        setup_once()
        if self.__tmp__:
            self.__tmp__ = util.maketemp() + '/'
            self.__yaml__ = self.__yaml__.replace("__tmp__", self.__tmp__)
        self.manager = MockManager(self.__yaml__, self.__class__.__name__, db_uri=self.database_uri)
        for config_function in self.config_functions:
            config_function(self.manager.config)
        if self.tasks_functions and 'tasks' in self.manager.config:
            for task_name, task_definition in self.manager.config['tasks'].items():
                for task_function in self.tasks_functions:
                    task_function(task_name, task_definition)


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

    def execute_task(self, name, abort_ok=False, options=None):
        """Use to execute one test task from config"""
        log.info('********** Running task: %s ********** ' % name)
        config = self.manager.config['tasks'][name]
        if hasattr(self, 'task'):
            if hasattr(self, 'session'):
                self.task.session.close() # pylint: disable-msg=E0203
        self.task = Task(self.manager, name, config=config, options=options)
        try:
            self.task.execute()
        except TaskAbort:
            if not abort_ok:
                raise

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
