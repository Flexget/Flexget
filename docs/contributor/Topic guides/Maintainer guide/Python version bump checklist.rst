=============================
Python version bump checklist
=============================

This checklist outlines the necessary steps to update the supported Python versions for the project.

Code Modifications
==================

- **Update ``requires-python``**:

  - Perform a batch search for ``requires-python`` across the project.
  - Increment the specified Python version to the new minimum supported version.

- **Update ``max_supported_python``**:

  - In the ``pyproject.toml`` file, locate the ``tool.pyproject-fmt.max_supported_python`` setting.
  - Increment the version to the new maximum supported Python version.

- **Update GitHub Actions Workflow**:

  - Open the ``.github/workflows/test.yml`` file.
  - In the ``matrix.python-version`` section, remove the oldest Python version and add the new latest supported version.

Codebase Verification
=====================

- **Search for Obsolete Version Mentions**:

  - Perform a batch search for the Python version being removed and the next subsequent version to identify any related TODOs or version-specific logic that needs to be updated. For example, search for ``python 3.10``, ``python3.10``, ``python 3.11``, and ``python3.11``.

- **Review ``sys.version_info`` Usage**:

  - Conduct a batch search for ``sys.version_info`` throughout the codebase.
  - Examine each instance to ensure that any version-specific logic is updated or removed as necessary.

Finalizing Changes
==================

- **Run Pre-commit**:

  - Execute ``pre-commit run -a`` to ensure all code formatting and quality checks pass with the new changes.

- **Bump Application Version**:

  - In the ``flexget/_version.py`` file, increment the minor version number.

Post-Merge Actions
==================

- **Update Wiki**:

  - After the pull request with these changes has been merged, update the `upgrade actions <https://flexget.com/en/UpgradeActions>`__ on the FlexGet wiki.
