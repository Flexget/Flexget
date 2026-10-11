.. highlight:: console

================================
Generating distribution archives
================================

`Distribution packages <https://packaging.python.org/en/latest/glossary/#term-Distribution-Package>`__
are archives that are uploaded to the Python Package Index and can be installed by
`pip <https://packaging.python.org/en/latest/key_projects/#pip>`__.

Steps to generate distribution packages
=======================================

#. To bundle the web UI, set the `BUNDLE_WEBUI_MODE` environment variable to `download` or `local`:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Unix
         :sync: Unix

         ::

            $ export BUNDLE_WEBUI_MODE=download

      .. tab-item:: Windows
         :sync: Windows

         ::

            $ $env:BUNDLE_WEBUI_MODE = 'download'

#. To provide extras, the ``BUILD_LOCKED_EXTRAS`` environment variable must be set:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Unix
         :sync: Unix

         ::

            $ export BUILD_LOCKED_EXTRAS=true

      .. tab-item:: Windows
         :sync: Windows

         ::

            $ $env:BUILD_LOCKED_EXTRAS = 'true'

   This environment variable prevents circular dependency resolution.
   Also see https://github.com/Flexget/Flexget/pull/4190.

#. Run::

   $ uv build
