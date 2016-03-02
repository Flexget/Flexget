from __future__ import unicode_literals, division, absolute_import
import logging
import os
import sys
import yaml
from contextlib import contextmanager

import mock
import pytest
from path import Path
from vcr import VCR

import flexget.logger
from flexget.manager import Manager
from flexget.plugin import load_plugins
from flexget.task import Task, TaskAbort

log = logging.getLogger('tests')


VCR_CASSETTE_DIR = os.path.join(os.path.dirname(__file__), 'cassettes')
VCR_RECORD_MODE = os.environ.get('VCR_RECORD_MODE', 'once')

vcr = VCR(cassette_library_dir=VCR_CASSETTE_DIR, record_mode=VCR_RECORD_MODE)


# --- These are the public fixtures tests can ask for ---

@pytest.fixture(scope='class')
def config(request):
    """
    If used inside a test class, uses the `config` class attribute of the class.
    This is used by `manager` fixture, and can be parametrized.
    """
    return request.cls.config


@pytest.yield_fixture()
def manager(request, config, filecopy):  # enforce filecopy is run before manager
    """
    Create a :class:`MockManager` for this test based on `config` argument.
    """
    mockmanager = MockManager(config, request.cls.__name__)
    yield mockmanager
    mockmanager.shutdown()
    mockmanager.__del__()


@pytest.fixture()
def execute_task(manager):
    """
    A function that can be used to execute and return a named task in `config` argument.
    """

    def execute(task_name, abort=False, options=None):
        """
        Use to execute one test task from config.

        :param abort: If `True` expect (and require) this task to abort.
        """
        log.info('********** Running task: %s ********** ' % task_name)
        config = manager.config['tasks'][task_name]
        task = Task(manager, task_name, config=config, options=options)

        try:
            if abort:
                with pytest.raises(TaskAbort):
                    task.execute()
            else:
                task.execute()
        finally:
            try:
                task.session.close()
            except Exception:
                pass
        return task

    return execute


@pytest.yield_fixture()
def use_vcr(request):
    """
    Decorator for test functions which go online. A vcr cassette will automatically be created and used to capture and
    play back online interactions. The nose 'vcr' attribute will be set, and the nose 'online' attribute will be set on
    it based on whether it might go online.

    The record mode of VCR can be set using the VCR_RECORD_MODE environment variable when running tests. Depending on
    the record mode, and the existence of an already recorded cassette, this decorator will also dynamically set the
    nose 'online' attribute.

    Keyword arguments to :func:`vcr.VCR.use_cassette` can be supplied.
    """
    module = request.module.__name__.split('tests.')[-1]
    class_name = request.cls.__name__
    cassette_name = '.'.join([module, class_name, request.function.__name__])
    cassette_path = os.path.join(VCR_CASSETTE_DIR, cassette_name)
    online = True
    # Set our nose online attribute based on the VCR record mode
    if vcr.record_mode == 'none':
        online = False
    elif vcr.record_mode == 'once':
        online = not os.path.exists(cassette_path)
    # TODO: Don't know if this is right, do some testing.
    pytest.mark.online(request)
    # If we are not going online, disable domain limiting during test
    if not online:
        request.function = mock.patch('flexget.utils.requests.limit_domains', new=mock.MagicMock())(request.function)
    if VCR_RECORD_MODE == 'off':
        yield None
    else:
        with vcr.use_cassette(path=cassette_path) as cassette:
            yield cassette

# --- End Public Fixtures ---


def pytest_configure(config):
    # register the filecopy marker
    config.addinivalue_line('markers',
        'filecopy(src, dst): mark test to copy a file from `src` to `dst` before running.')


def pytest_runtest_setup(item):
    # Add the filcopy fixture to any test marked with filecopy
    envmarker = item.get_marker('filecopy')
    if envmarker is not None:
        item.add_marker(pytest.mark.usefixtures('filecopy'))


@pytest.fixture()
def filecopy(request, tmpdir):
    marker = request.node.get_marker('filecopy')
    if marker is not None:
        src, dst = marker.args
        dst = Path(dst.replace('__tmp__', tmpdir.strpath))
        out_files = []
        for f in Path().glob(src):
            if dst.isdir():
                dst = dst / f.basename()
            f.copy(dst)
            out_files.append(dst)

        def fin():
            for f in out_files:
                f.remove()

        request.addfinalizer(fin)


@pytest.fixture(scope='session', autouse=True)
def setup_once(pytestconfig, request):
    os.chdir(os.path.join(pytestconfig.rootdir.strpath, 'tests'))
    flexget.logger.initialize(True)
    MockManager('tasks: {}', 'init')  # This makes sure our template environment is set up before any tests are run
    # VCR.py mocked functions not handle ssl verification well. Older versions of urllib3 don't have this
    # if VCR_RECORD_MODE != 'off':
    #     try:
    #         from requests.packages.urllib3.exceptions import SecurityWarning
    #         warnings.simplefilter('ignore', SecurityWarning)
    #     except ImportError:
    #         pass
    load_plugins()


@pytest.fixture(autouse=True)
def setup_loglevel(pytestconfig, caplog):
    # set logging level according to pytest verbosity
    level = logging.DEBUG
    if pytestconfig.getoption('verbose') == 1:
        level = flexget.logger.TRACE
    elif pytestconfig.getoption('quiet') == 1:
        level = logging.INFO
    logging.getLogger().setLevel(level)
    caplog.setLevel(level)


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

