.. _Triggering a manual release:

===========================
Triggering a manual release
===========================

#. Navigate to the `Trigger Deploy <https://github.com/Flexget/Flexget/actions/workflows/nightly.yml>`_ workflow page.
#. Click the ``Run workflow`` button to begin the process.
#. Retain the default selection to execute the workflow from the ``develop`` branch.
#. The deployment process will commence accordingly.

You may monitor the progress and outcome of the deployment on the
`Deployments Page <https://github.com/Flexget/Flexget/deployments/production>`_.

Manual Docker release from a local machine
==========================================

To build and push a Docker image to Docker Hub directly from your local machine,
use the provided release script::

   $ ./scripts/manual_release.sh

The script requires Docker Hub credentials. The easiest way to provide them is via a
``.env`` file in the repo root (see :ref:`Environment variables`):

.. code-block:: text

   DH_USERNAME=myusername
   DH_PASSWORD=mypassword-or-access-token

Optional variables:

- ``IMAGE_NAME`` — full repository name (default: ``$DH_USERNAME/flexget``)
- ``IMAGE_TAG`` — tag to apply (default: current version from ``flexget/_version.py``)
- ``V2_WEBUI_LOCATION`` — URL or local path to the v2 WebUI ``dist.zip``

The script will:

#. Build the Python distribution with ``uv build``
#. Build the Docker image from the ``Dockerfile``
#. Log in to Docker Hub, push both the versioned tag and ``latest``, then log out
