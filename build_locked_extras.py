import os
import subprocess
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from hatchling.metadata.plugin.interface import MetadataHookInterface


def update_metadata_with_locked(
    metadata: MutableMapping[str, Any], root: Path, groups: Optional[list[str]] = None
) -> None:  # pragma: no cover
    """Inplace update the metadata(pyproject.toml) with the locked dependencies.

    Args:
        metadata (dict[str, Any]): The metadata dictionary
        root (Path): The path to the project root
        groups (list[str], optional): The groups to lock.

    """
    lockfile = root / "uv.lock"
    if not lockfile.exists():
        print(f"The lockfile doesn't exist, skip locking dependencies {root}")
        sys.exit(1)
    with lockfile.open("rb") as f:
        lockfile_content = tomllib.load(f)

    for pkg in lockfile_content["package"]:
        if pkg["name"] == metadata["name"]:
            lockfile_metadata = pkg
            break
    else:
        print(f"`{metadata['name']}` not found in the lock file")
        return
    groups = groups or []
    print(f"Adding extras with locked dependencies: {', '.join(groups)}")
    for group in [*groups, "locked"]:
        if group == "locked":
            args = []
        else:
            # TODO: This check (and the above code to read lockfile_metadata) can come out if uv starts handling it
            # https://github.com/astral-sh/uv/issues/10882
            if group not in lockfile_metadata["dev-dependencies"]:
                print(
                    f"Group `{group}` is not defined in the project's `dependency-group` table "
                    "(or the lock file is stale)"
                )
                sys.exit(1)
            args = [f"--only-group={group}"]
        try:
            export = subprocess.check_output(
                [
                    "uv",
                    "--color=never",
                    "export",
                    "--frozen",
                    "--no-hashes",
                    "--no-emit-project",
                    *args,
                ],
                cwd=root,
                timeout=5,
                encoding="utf-8",
                stderr=subprocess.PIPE,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            print(f"Failed to export locked dependencies for `{group}`: {exc.stderr}")
            sys.exit(1)
        requirements = [line for line in export.splitlines() if not line.startswith("#")]
        metadata.setdefault("optional-dependencies", {})[group] = requirements


class BuildLockedMetadataHook(MetadataHookInterface):
    PLUGIN_NAME = "build-locked-extras"

    def update(self, metadata: dict) -> None:
        if os.environ.get("BUILD_LOCKED_EXTRAS") not in ["1", "true"]:
            return
        update_metadata_with_locked(metadata, Path(self.root), self.config.get("locked-groups"))
