from importlib.util import find_spec
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

if find_spec("paramiko"):
    from tests.sftp.test_sftp_server import TestSFTPServerController


@pytest.fixture
def sftp_root(tmp_path: "Path"):
    sftp_root = tmp_path / "sftp_root"
    sftp_root.mkdir()
    return sftp_root


@pytest.fixture
def sftp(sftp_root: "Path"):
    test_server = TestSFTPServerController(sftp_root)
    yield test_server
    test_server.kill()
