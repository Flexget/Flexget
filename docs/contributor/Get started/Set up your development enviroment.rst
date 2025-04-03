.. highlight:: console

===================================
Set up your development environment
===================================

Clone the repository
====================

First off you'll need your copy of the ``Flexget`` codebase.
You can clone it for local development like so:

1. **Fork the repository**, so you have your own copy on GitHub.
   See the `GitHub forking guide <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo>`__ for more information.
2. **Clone the repository locally** so that you have a local copy to work from::

      $ git clone https://github.com/{{ YOUR USERNAME }}/Flexget
      $ cd Flexget

Install your tools
==================

Setup ``uv``
------------

To start, install ``uv``:

.. tab-set::
   :sync-group: os

   .. tab-item:: macOS and Linux
      :sync: macos

      ::

         $ curl -LsSf https://astral.sh/uv/install.sh | sh

   .. tab-item:: Windows
      :sync: windows

      ::

         $ powershell -ExecutionPolicy ByPass -c 'irm https://astral.sh/uv/install.ps1 | iex'

Install the project and commonly used development dependencies
--------------------------------------------------------------

To install the project along with the commonly used development dependencies, run the
following command::

   $ uv sync

.. _Install additional testing dependencies:

Install additional testing dependencies
---------------------------------------

If you need to run specific FlexGet tests locally, additional testing dependencies must be
installed. These dependencies are listed under the ``plugin-test`` group in ``pyproject.toml``
and can be conveniently installed with::

   $ uv sync --group plugin-test --inexact

.. attention::
   On Windows, running specific FlexGet tests requires enabling ``Developer Mode``.
   To do this, open ``Settings``, search for ``Developer Mode``, and toggle the option on.

.. seealso::
   :ref:`Run and write tests`

.. _Install the docs dependencies:

Install the docs dependencies
-----------------------------

If you want to build the documentaion locally, additional docs dependencies must be installed::

   $ uv sync --group doc --inexact

.. seealso::
   :ref:`Docstrings & documentation`

Setup ``pre-commit``
--------------------

``pre-commit`` allows us to run several checks on the codebase every time a new Git commit is made.
This ensures standards and basic quality control for our code.

.. note::
   If you don't want to prepend ``uv run`` to the ``pre-commit`` command, you can also choose to
   enter the virtual environment:

   .. tab-set::
      :sync-group: os

      .. tab-item:: macOS and Linux
         :sync: macos

         ::

            $ source .venv/bin/activate

      .. tab-item:: Windows
         :sync: windows

         ::

            $ Set-ExecutionPolicy Unrestricted -Scope CurrentUser
            $ .venv\Scripts\activate.ps1

Navigate to this repository’s folder and activate it like so::

   $ uv run pre-commit install

.. _link to upstream:

Link your repository to the upstream repo
=========================================

::

   $ git remote add upstream https://github.com/Flexget/Flexget.git

``upstream`` here is just the arbitrary name we’re using to refer to the main
``Flexget`` repository.

Just for your own satisfaction, show yourself that you now have a new ‘remote’,
with ``git remote -v show``, giving you something like::

   upstream     https://github.com/Flexget/Flexget.git (fetch)
   upstream     https://github.com/Flexget/Flexget.git (push)
   origin       git@github.com:your-user-name/Flexget.git (fetch)
   origin       git@github.com:your-user-name/Flexget.git (push)
