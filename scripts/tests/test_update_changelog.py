import filecmp
import os
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.update_changelog import update_changelog


@pytest.mark.parametrize(
    "n",
    [
        1,
        2,
    ],
)
def test_update_changelog(tmp_path, n):
    shutil.copy(Path(__file__).parent / "update_changelog" / f"test_{n}/ChangeLog.md", tmp_path)
    ZipFile(Path(__file__).parent / "update_changelog" / f"test_{n}" / "repo.zip").extractall(
        tmp_path
    )
    os.chdir(tmp_path)
    update_changelog(Path("ChangeLog.md"))
    assert filecmp.cmp(
        "ChangeLog.md",
        Path(__file__).parent / "update_changelog" / f"test_{n}" / "new_ChangeLog.md",
    )
