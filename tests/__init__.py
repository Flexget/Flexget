#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import inspect
import functools
import os
import sys
import logging

import mock
from nose.plugins.attrib import attr

import flexget.logger
from flexget.task import Task, TaskAbort
from tests import util

log = logging.getLogger('tests')


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
