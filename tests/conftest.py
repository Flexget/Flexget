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


def pytest_generate_tests(metafunc):
    """
    For any tests in a class with a `config_params` argument, the config will pe parametrized.

    The test will be run multiple times with the config rendered against the values in the `config_params` dict.
    """
    if getattr(metafunc.cls, 'config_params', None):
        config_params = metafunc.cls.config_params
        if isinstance(config_params, dict):
            config_params = config_params.items()
        idlist, contexts = zip(*config_params)
        config_template = Template(metafunc.cls.config)
        configs = [config_template.render(context) for context in contexts]
        metafunc.parametrize('config', configs, ids=idlist, scope="class")


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
    return request.cls.config


@pytest.fixture()
def manager(request, config):
    mockmanager = MockManager(config, request.cls.__name__)

    def fin():
        mockmanager.shutdown()
        mockmanager.__del__()

    request.addfinalizer(fin)
    return mockmanager


@pytest.fixture()
def execute_task(manager):

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
