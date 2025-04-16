===============
Making releases
===============

Our goals
=========

Our release policy describes how we decide when to make a new public release of the tool so that
users may use new features and improvements. It tries to balance these goals:

- Release relatively frequently, so that we provide a continuous stream of improvement to users
  that use the tool, and minimize the effort needed to upgrade.
- Do not surprise people (especially with negative surprises) and provide time for users to
  provide feedback about upcoming features.
- Minimize the toil and complexity associated with releases, and reduce information silos and
  bottlenecks associated with them.

Making a release
================

Flexget is configured to undergo automated nightly builds at 15:00 UTC,
contingent upon the presence of new commits on the ``develop`` branch.

Collaborators with write access to this repository are also empowered
to initiate a manual release when necessary.

Steps to initiate a manual release
----------------------------------

#. Navigate to the `Trigger Deploy <https://github.com/Flexget/Flexget/actions/workflows/nightly.yml>`_ workflow page.
#. Click the **Run workflow** button to begin the process.
#. Retain the default selection to execute the workflow from the ``develop`` branch.
#. The deployment process will commence accordingly.

You may monitor the progress and outcome of the deployment on the
`Deployments Page <https://github.com/Flexget/Flexget/deployments/production>`_.

Choosing a version increment
============================

We adhere to ``PEP 440`` to determine whether a version bump should be major, minor, or a patch.

``PEP 440`` is the official Python versioning standard, providing a consistent and structured
approach to defining and comparing package versions. It aligns with semantic versioning principles,
where major versions introduce breaking changes, minor versions add backward-compatible features,
and patch versions address bug fixes. Additionally, it supports pre-releases, post-releases,
and development versions, ensuring a clear and predictable versioning strategy.
