import argparse
import itertools
import logging
import os
import re
import shutil
from contextlib import contextmanager, suppress
from http import client
from pathlib import Path
from typing import Any, Callable, Optional, Union
from unittest import mock

import flask
import jsonschema
import pytest
import requests
import yaml
from _pytest.logging import caplog as _caplog  # noqa: F401 pytest fixtures look unused
from loguru import logger
from vcr import VCR
from vcr.stubs import VCRHTTPConnection, VCRHTTPSConnection

import flexget.log
from flexget import plugin
from flexget.api import api_app
from flexget.event import event
from flexget.manager import Manager, Session
from flexget.plugin import load_plugins
from flexget.task import Task, TaskAbort
from flexget.webserver import User

logger = logger.bind(name='tests')

VCR_CASSETTE_DIR = os.path.join(os.path.dirname(__file__), 'cassettes')
VCR_RECORD_MODE = os.environ.get('VCR_RECORD_MODE', 'once')

vcr = VCR(
    cassette_library_dir=VCR_CASSETTE_DIR,
    record_mode=VCR_RECORD_MODE,
    custom_patches=(
        (client, 'HTTPSConnection', VCRHTTPSConnection),
        (client, 'HTTPConnection', VCRHTTPConnection),
    ),
)


# --- These are the public fixtures tests can ask for ---


@pytest.fixture(scope='class')
def config(request):
    """If used inside a test class, uses the `config` class attribute of the class.

    This is used by `manager` fixture, and can be parametrized.
    """
    return request.cls.config


@pytest.fixture
def manager(
    request, config, caplog, monkeypatch, filecopy, tmp_path_factory
):  # enforce filecopy is run before manager
    """Create a :class:`MockManager` for this test based on `config` argument."""
    config = config.replace('__tmp__', request.getfixturevalue('tmp_path').as_posix())
    try:
        mockmanager = MockManager(config, request.cls.__name__, tmp_path_factory.mktemp('manager'))
    except Exception:
        # Since we haven't entered the test function yet, pytest won't print the logs on failure. Print them manually.
        print(caplog.text)
        raise
    yield mockmanager
    mockmanager.shutdown()


@pytest.fixture
def execute_task(manager: Manager) -> Callable[..., Task]:
    """Can be used to execute and return a named task in `config` argument."""

    def execute(
        task_name: str,
        abort: bool = False,
        options: Optional[Union[dict, argparse.Namespace]] = None,
    ) -> Task:
        """Use to execute one test task from config.

        :param task_name: Name of task to execute.
        :param abort: If `True` expect (and require) this task to abort.
        :param options: Options for the execution.
        """
        logger.info('********** Running task: {} ********** ', task_name)
        config = manager.config['tasks'][task_name]
        task = Task(manager, task_name, config=config, options=options)

        try:
            if abort:
                with pytest.raises(TaskAbort):
                    task.execute()
            else:
                task.execute()
        finally:
            with suppress(Exception):
                task.session.close()
        return task

    return execute


@pytest.fixture
def use_vcr(request, monkeypatch):
    """Be applied automatically to any test using the `online` mark.

    It will record and playback network sessions using VCR.

    The record mode of VCR can be set using the VCR_RECORD_MODE environment variable when running tests.
    """
    if VCR_RECORD_MODE == 'off':
        yield None
    else:
        module = request.module.__name__.split('tests.')[-1]
        class_name = request.cls.__name__
        cassette_name = f'{module}.{class_name}.{request.function.__name__}'
        cassette_path = os.path.join(VCR_CASSETTE_DIR, cassette_name)
        online = True
        if vcr.record_mode == 'none':
            online = False
        elif vcr.record_mode == 'once':
            online = not os.path.exists(cassette_path)
        # If we are not going online, disable domain limiting during test
        if not online:
            logger.debug('Disabling domain limiters during VCR playback.')
            monkeypatch.setattr('flexget.utils.requests.limit_domains', mock.Mock())
        with vcr.use_cassette(path=cassette_path) as cassette:
            yield cassette


@pytest.fixture
def api_client(manager) -> 'APIClient':
    with Session() as session:
        user = session.query(User).first()
        if not user:
            user = User(name='flexget', password='flexget')
            session.add(user)
            session.commit()
        return APIClient(user.token)


@pytest.fixture
def schema_match(manager) -> Callable[[dict, Any], list[dict]]:
    """Enable verifying JSON Schema.

    Return a list of validation error dicts. List is empty if no errors occurred.
    """

    def match(schema: dict, response: Any) -> list[dict]:
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(response))
        return [{'value': list(e.path), 'message': e.message} for e in errors]

    return match


@pytest.fixture
def link_headers(manager) -> Callable[[flask.Response], dict[str, dict]]:
    """Parse link headers and return them in dict form."""

    def headers(response: flask.Response) -> dict[str, dict]:
        links = {}
        for link in requests.utils.parse_header_links(response.headers.get('link')):
            url = link['url']
            page = int(re.search(r'(?<!per_)page=(\d)', url).group(1))
            links[link['rel']] = {'url': url, 'page': page}
        return links

    return headers


@pytest.fixture(autouse=True)
def caplog(pytestconfig, _caplog):  # noqa: F811
    """Override caplog so that we can send loguru messages to logging for compatibility."""
    # set logging level according to pytest verbosity
    level = logger.level('DEBUG')
    if pytestconfig.getoption('verbose') == 1:
        level = logger.level('TRACE')
    elif pytestconfig.getoption('quiet', None) == 1:
        level = logger.level('INFO')

    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), level=level.no, format="{message}", catch=False)
    _caplog.set_level(level.no)
    yield _caplog
    logger.remove(handler_id)


# --- End Public Fixtures ---


def pytest_runtest_setup(item):
    # Add the filcopy fixture to any test marked with filecopy
    if item.get_closest_marker('filecopy'):
        item.fixturenames.append('filecopy')
    # Add the online marker to tests that will go online
    if item.get_closest_marker('online'):
        item.fixturenames.append('use_vcr')
    else:
        item.fixturenames.append('no_requests')


@pytest.fixture
def filecopy(request):
    out_files = []
    for marker in request.node.iter_markers('filecopy'):
        copy_list = marker.args[0] if len(marker.args) == 1 else [marker.args]

        for sources, dst in copy_list:
            if isinstance(sources, str):
                sources = [sources]
            dst = dst.replace('__tmp__', request.getfixturevalue('tmp_path').as_posix())
            dst = Path(dst)
            for f in itertools.chain(*(Path().glob(src) for src in sources)):
                dest_path = dst
                if dest_path.is_dir():
                    dest_path = dest_path / f.name
                logger.debug('copying {} to {}', f, dest_path)
                if not os.path.isdir(os.path.dirname(dest_path)):
                    os.makedirs(os.path.dirname(dest_path))
                if os.path.isdir(f):
                    shutil.copytree(f, dest_path)
                else:
                    shutil.copy(f, dest_path)
                out_files.append(dest_path)
    yield
    if out_files:
        for f in out_files:
            try:
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    f.unlink()
            except OSError as e:
                print(f"couldn't remove {f}: {e}")


@pytest.fixture
def no_requests(monkeypatch):
    online_funcs = ['requests.sessions.Session.request', 'http.client.HTTPConnection.request']

    # Don't monkey patch HTTPSConnection if ssl not installed as it won't exist in backports
    try:
        import ssl  # noqa: F401
        from ssl import SSLContext  # noqa: F401

        online_funcs.append('http.client.HTTPSConnection.request')
    except ImportError:
        pass

    online_funcs.extend(
        ['http.client.HTTPConnection.request', 'http.client.HTTPSConnection.request']
    )

    for func in online_funcs:
        monkeypatch.setattr(
            func, mock.Mock(side_effect=Exception('Online tests should use @pytest.mark.online'))
        )


@pytest.fixture(scope='session', autouse=True)
def setup_once(pytestconfig, request, tmp_path_factory):
    #    os.chdir(os.path.join(pytestconfig.rootdir.strpath, 'flexget', 'tests'))
    flexget.log.initialize(True)
    m = MockManager(
        'tasks: {}', 'init', tmp_path_factory.mktemp('manager')
    )  # This makes sure our template environment is set up before any tests are run
    m.shutdown()
    logging.getLogger().setLevel(logging.DEBUG)
    load_plugins()


@pytest.fixture(autouse=True)
def chdir(pytestconfig, request):
    """Change current working directory to that module location by marking test with chdir flag.

    Task configuration can then assume this being location for relative paths
    """
    if 'chdir' in request.fixturenames:
        os.chdir(os.path.dirname(request.module.__file__))


@pytest.fixture(autouse=True)
def clear_caches():
    """Make sure cached_input, and other caches are cleared between tests."""
    from flexget.utils.tools import TimedDict

    TimedDict.clear_all()


class CrashReport(Exception):
    def __init__(self, message: str, crash_log: str):
        self.message = message
        self.crash_log = crash_log


class MockManager(Manager):
    unit_test = True

    def __init__(
        self, config_text: str, config_name: str, tmp_path: Path, db_uri: Optional[str] = None
    ):
        self._config_name = config_name
        self._tmp_path = tmp_path
        self.config_text = config_text
        self._db_uri = db_uri or 'sqlite:///:memory:'
        super().__init__(['execute'])
        self.database_uri = self._db_uri
        logger.debug('database_uri: {}', self.database_uri)
        self.initialize()

    def _init_config(self, *args, **kwargs):
        """Override configuration loading."""
        self._config_path = self._tmp_path / self._config_name

    def load_config(self, *args, **kwargs):
        """Just load our config from the text passed in on init."""
        config = yaml.safe_load(self.config_text) or {}
        self.update_config(config)

    @property
    def conn(self):
        return self.engine.connect()

    # no lock files with unit testing
    @contextmanager
    def acquire_lock(self, **kwargs):
        self._has_lock = True
        yield

    def release_lock(self):
        pass

    def crash_report(self):
        # We don't want to silently swallow crash reports during unit tests
        logger.opt(exception=True).error('Crash Report Traceback:')
        raise CrashReport(
            'Crash report created during unit test, check log for traceback.',
            flexget.log.debug_buffer,
        )

    def shutdown(self, finish_queue=True):
        super().shutdown(finish_queue=finish_queue)
        self._shutdown()


# Perhaps this bit should go somewhere else... The way reruns work can be complicated, and was causing issues in
# some cases. This plugin should run on all tests in the suite, to make sure certain phases aren't getting
# called twice. https://github.com/Flexget/Flexget/issues/3254
class DoublePhaseChecker:
    @staticmethod
    def on_phase(task, phase):
        if getattr(task, f'did_{phase}', None):
            raise RuntimeError(f'{phase} phase should not run twice')
        setattr(task, f'did_{phase}', True)

    def on_task_start(self, task, config):
        self.on_phase(task, 'start')

    def on_task_prepare(self, task, config):
        self.on_phase(task, 'prepare')

    def on_task_exit(self, task, config):
        self.on_phase(task, 'exit')


@event('plugin.register')
def register_plugin():
    plugin.register(DoublePhaseChecker, 'test_dobule_phase', api_ver=2, debug=True, builtin=True)


class APIClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = api_app.test_client()

    def _append_header(self, key, value, kwargs):
        if 'headers' not in kwargs:
            kwargs['headers'] = {}

        kwargs['headers'][key] = value

    def json_post(self, *args, **kwargs) -> flask.Response:
        self._append_header('Content-Type', 'application/json', kwargs)
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)
        return self.client.post(*args, **kwargs)

    def json_put(self, *args, **kwargs) -> flask.Response:
        self._append_header('Content-Type', 'application/json', kwargs)
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)
        return self.client.put(*args, **kwargs)

    def json_patch(self, *args, **kwargs) -> flask.Response:
        self._append_header('Content-Type', 'application/json', kwargs)
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)
        return self.client.patch(*args, **kwargs)

    def get(self, *args, **kwargs) -> flask.Response:
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)

        return self.client.get(*args, **kwargs)

    def delete(self, *args, **kwargs) -> flask.Response:
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)

        return self.client.delete(*args, **kwargs)

    def json_delete(self, *args, **kwargs) -> flask.Response:
        self._append_header('Content-Type', 'application/json', kwargs)
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)
        return self.client.delete(*args, **kwargs)

    def head(self, *args, **kwargs) -> flask.Response:
        if kwargs.get('auth', True):
            self._append_header('Authorization', f'Token {self.api_key}', kwargs)

        return self.client.head(*args, **kwargs)
