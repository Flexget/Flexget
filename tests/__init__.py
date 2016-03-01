#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import inspect
import functools
import os
import sys
import logging

import mock
from nose.plugins.attrib import attr
from vcr import VCR

import flexget.logger
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


def use_vcr(func=None, **kwargs):
    """
    Decorator for test functions which go online. A vcr cassette will automatically be created and used to capture and
    play back online interactions. The nose 'vcr' attribute will be set, and the nose 'online' attribute will be set on
    it based on whether it might go online.

    The record mode of VCR can be set using the VCR_RECORD_MODE environment variable when running tests. Depending on
    the record mode, and the existence of an already recorded cassette, this decorator will also dynamically set the
    nose 'online' attribute.

    Keyword arguments to :func:`vcr.VCR.use_cassette` can be supplied.
    """
    if func is None:
        # When called with kwargs, e.g. @use_vcr(inject_cassette=True)
        return functools.partial(use_vcr, **kwargs)
    module = func.__module__.split('tests.')[-1]
    class_name = inspect.stack()[1][3]
    cassette_name = '.'.join([module, class_name, func.__name__])
    kwargs.setdefault('path', cassette_name)
    cassette_path = os.path.join(VCR_CASSETTE_DIR, cassette_name)
    online = True
    # Set our nose online attribute based on the VCR record mode
    if vcr.record_mode == 'none':
        online = False
    elif vcr.record_mode == 'once':
        online = not os.path.exists(cassette_path)
    func = attr(online=online, vcr=True)(func)
    # If we are not going online, disable domain limiting during test
    if not online:
        func = mock.patch('flexget.utils.requests.limit_domains', new=mock.MagicMock())(func)
    if VCR_RECORD_MODE == 'off':
        return func
    else:
        return vcr.use_cassette(**kwargs)(func)




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

    @classmethod
    def setup_class(cls):
        setup_once()
        cls.log = log
        cls.manager = None
        cls.task = None
        cls.base_path = os.path.dirname(__file__)

    def execute(self, task_name, abort_ok=False, options=None):
        """Use to execute one test task from config"""
        log.info('********** Running task: %s ********** ' % task_name)
        manager = MockManager(self.config, self.__class__.__name__)
        config = manager.config['tasks'][task_name]

        if hasattr(self, 'task'):
            if hasattr(self, 'session'):
                self.task.session.close() # pylint: disable-msg=E0203

        self.task = Task(manager, task_name, config=config, options=options)

        try:
            self.task.execute()
        except TaskAbort:
            if not abort_ok:
                raise
        finally:
            try:
                self.task.session.close()
            except:
                pass
            manager.shutdown()
            manager.__del__()

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


class BaseTest(object):
    config = None



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
