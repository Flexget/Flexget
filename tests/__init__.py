#!/usr/bin/python

from __future__ import unicode_literals, division, absolute_import
import os
import sys
import logging


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


