.. highlight:: console

=============================
Development environment setup
=============================

Cloning the repository
======================

First off you'll need your copy of the ``Flexget`` codebase.
You can clone it for local development like so:

1. **Fork the repository**, so you have your own copy on GitHub.
   See the `GitHub forking guide <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo>`__ for more information.
2. **Clone the repository locally** so that you have a local copy to work from::

      $ git clone https://github.com/{{ YOUR USERNAME }}/Flexget
      $ cd Flexget

Installing ``uv``
=================

To start, install ``uv``:

.. tab-set::
   :sync-group: os

   .. tab-item:: Unix
      :sync: Unix

      ::

         $ curl -LsSf https://astral.sh/uv/install.sh | sh

   .. tab-item:: Windows
      :sync: Windows

      ::

         $ powershell -ExecutionPolicy ByPass -c 'irm https://astral.sh/uv/install.ps1 | iex'

Installing dependencies using ``uv sync``
=========================================

Installing the project and commonly used development dependencies
-----------------------------------------------------------------

To install the project along with the commonly used development dependencies, run the
following command::

   $ uv sync

.. note::

   By default, an exact sync is performed: ``uv`` removes any packages not explicitly specified in
   the command. Use the ``--inexact`` flag to retain extraneous packages.

   For example, if you previously installed additional testing dependencies using ``uv sync
   --group plugin-test``, and then later run ``uv sync --group docs`` to install documentation
   dependencies, the testing dependencies from the ``plugin-test`` group will be removed. To
   preserve the previously installed testing dependencies while adding the docs dependencies,
   you should use::

      $ uv sync --group docs --inexact

.. _Installing optional dependencies:

Installing optional dependencies
--------------------------------

To use and test certain plugins, you need to install optional dependencies.
These can be installed using "extras".

Available extras include ``qbittorrent``, ``sftp``, and ``telegram``.
For example, to install ``qbittorrent`` and ``telegram``, run::

   $ uv sync --group qbittorrent --group telegram

All extras are listed in the ``[project.dependency-groups]`` table within the ``pyproject.toml``
file. For convenience, an ``all`` extra is also provided, which will install all the optional
dependencies at once. You can install it using::

   $ uv sync --group all

.. note::
   On Windows, running specific FlexGet tests requires enabling ``Developer Mode``.
   To do this, open ``Settings``, search for ``Developer Mode``, and toggle the option on.

.. seealso::
   :ref:`Running and writing tests`

.. _Installing the docs dependencies:

Installing the docs dependencies
--------------------------------

If you want to build the documentaion locally, additional docs dependencies must be installed::

   $ uv sync --group docs

.. seealso::
   :ref:`Docstrings and documentation`

Setting up ``pre-commit``
=========================

``pre-commit`` allows us to run several checks on the codebase every time a new Git commit is made.
This ensures standards and basic quality control for our code.

Navigate to this repository’s folder and activate it like so::

   $ uv run pre-commit install

By default, ``pre-commit`` runs its checks on staged files.
If you've modified the ``pre-commit`` hooks configuration—for example, by adding a new ``Ruff``
rule—you'll need to run it on all files manually instead::

   $ uv run pre-commit run -a

.. note::
   To avoid having to prepend ``uv run`` to the ``pre-commit`` command, you can either globally
   install ``pre-commit`` or activate the virtual environment:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Unix
         :sync: Unix

         ::

            $ source .venv/bin/activate

      .. tab-item:: Windows
         :sync: Windows

         ::

            $ Set-ExecutionPolicy Unrestricted -Scope CurrentUser
            $ .venv\Scripts\activate.ps1

.. _linking to upstream:

Linking your repository to the upstream repo
============================================

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
