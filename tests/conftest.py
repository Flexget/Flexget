from __future__ import unicode_literals, division, absolute_import
import logging
import os
import sys
import yaml
from contextlib import contextmanager
from copy import deepcopy

import pytest
from jinja2 import Template

import flexget.logger
from flexget.manager import Manager
from flexget.plugin import load_plugins
from flexget.task import Task, TaskAbort

log = logging.getLogger('tests')


@pytest.fixture(scope='session', autouse=True)
def setup_once():
    flexget.logger.initialize(True)
    #setup_logging_level()
    # VCR.py mocked functions not handle ssl verification well. Older versions of urllib3 don't have this
    # if VCR_RECORD_MODE != 'off':
    #     try:
    #         from requests.packages.urllib3.exceptions import SecurityWarning
    #         warnings.simplefilter('ignore', SecurityWarning)
    #     except ImportError:
    #         pass
    load_plugins()


# --- These are the public fixtures tests can ask for ---

@pytest.fixture()
def config(request):
    """
    If used inside a test class, uses the `config` class attribute of the class.
    This is used by `manager` fixture, and can be parametrized.
    """
    return request.cls.config


@pytest.fixture()
def manager(request, config):
    """
    Create a :class:`MockManager` for this test based on `config` argument.
    """
    mockmanager = MockManager(config, request.cls.__name__)

    def fin():
        mockmanager.shutdown()
        mockmanager.__del__()

    request.addfinalizer(fin)
    return mockmanager


@pytest.fixture()
def execute_task(manager):
    """
    A function that can be used to execute and return a named task in `config` argument.
    """

    def execute(task_name, abort_ok=False, options=None):
        """Use to execute one test task from config"""
        log.info('********** Running task: %s ********** ' % task_name)
        config = manager.config['tasks'][task_name]
        task = Task(manager, task_name, config=config, options=options)

        try:
            task.execute()
        except TaskAbort:
            if not abort_ok:
                raise
        finally:
            try:
                task.session.close()
            except:
                pass
        return task

    return execute

# --- End Public Fixtures ---


class CrashReport(Exception):
    pass


class MockManager(Manager):
    unit_test = True

    def __init__(self, config_text, config_name, db_uri=None):
        self.config_text = config_text
        self._db_uri = db_uri or 'sqlite:///:memory:'
        super(MockManager, self).__init__(['execute'])
        self.config_name = config_name
        self.database_uri = self._db_uri
        log.debug('database_uri: %s' % self.database_uri)
        self.initialize()

    def find_config(self, *args, **kwargs):
        """
        Override configuration loading
        """
        self.config_base = os.path.dirname(os.path.abspath(sys.path[0]))

    def load_config(self):
        """
        Just load our config from the text passed in on init
        """
        config = yaml.safe_load(self.config_text) or {}
        self.update_config(config)

    # no lock files with unit testing
    @contextmanager
    def acquire_lock(self, **kwargs):
        self._has_lock = True
        yield

    def release_lock(self):
        pass

    def crash_report(self):
        # We don't want to silently swallow crash reports during unit tests
        log.error('Crash Report Traceback:', exc_info=True)
        raise CrashReport('Crash report created during unit test, check log for traceback.')
