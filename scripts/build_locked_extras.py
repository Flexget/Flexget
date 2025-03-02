import os
import subprocess
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Optional

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
    groups = groups or []
    print(f"Adding extras with locked dependencies: {', '.join(groups)}")
    for group in [*groups, "locked"]:
        args = [] if group == "locked" else [f"--only-group={group}"]
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
        if not requirements:
            # TODO: We can remove this if uv starts checking the existence of groups itself.
            # https://github.com/astral-sh/uv/issues/10882
            print(
                f"There does not appear to be any requirements for group `{group}`, does it exist?"
            )
            sys.exit(1)
        metadata.setdefault("optional-dependencies", {})[group] = requirements


class BuildLockedMetadataHook(MetadataHookInterface):
    PLUGIN_NAME = "build-locked-extras"

    def update(self, metadata: dict) -> None:
        if os.environ.get("BUILD_LOCKED_EXTRAS") not in ["1", "true"]:
            return
        update_metadata_with_locked(metadata, Path(self.root), self.config.get("locked-groups"))
