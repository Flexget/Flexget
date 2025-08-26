.. _Running and writing tests:

=========================
Running and writing tests
=========================

Pull requests (PRs) that modify code should either have new tests, or modify existing
tests to fail before the PR and pass afterwards. Tests for a module should ideally cover
all code in that module, i.e., statement coverage should be at 100%.

Before reading this article, you should have a basic understanding of
`pytest <https://docs.pytest.org/>`__.

Running the tests
=================

If you need to run specific FlexGet tests locally, :ref:`additional testing dependencies
<Installing optional dependencies>` must be installed.

To run all tests, simply execute:

.. code:: console

   $ uv run pytest

If you want to run tests in parallel to speed up the process, run:

.. code:: console

   $ uv run pytest -n logical --dist loadgroup

If you want to run a specific test within a module or run all tests in a class,
see `specifying which tests to run <https://docs.pytest.org/en/stable/how-to/usage.html>`__.

.. note::
   To avoid having to prepend ``uv run`` to your commands, you can activate the virtual
   environment instead:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Unix
         :sync: Unix

         .. code:: console

            $ source .venv/bin/activate

      .. tab-item:: Windows
         :sync: Windows

         .. code:: console

            $ Set-ExecutionPolicy Unrestricted -Scope CurrentUser
            $ .venv\Scripts\activate.ps1

Testing a plugin
================

We'll go through an example, starting with creating a plugin and then writing tests for it.

Creating a plugin
-----------------

Create new file called ``flexget/plugins/output/hello.py``.

Within this file we will add our plugin.

.. testcode::

   from flexget import plugin
   from flexget.event import event


   class Hello:
       pass

   @event('plugin.register')
   def register_plugin():
       plugin.register(Hello, 'hello', api_ver=2)

Creating a test for it
----------------------

Write a new test case called ``tests/test_hello.py``.

.. testcode::

   class TestHello:

       config = """
           tasks:
             test:
               mock:                 # let's use this plugin to create test data
                 - {title: 'foobar'} # we can omit url if we do not care about it, in this case mock will add random url
               hello: yes            # our plugin, no relevant configuration yet ...
       """

       # The flexget test framework provides the execute_task fixture, which is a function to run tasks
       def test_feature(self, execute_task):
         # run the task
         execute_task('test')

Try running the test with pytest:

.. code:: console

  $ uv run pytest tests/test_hello.py

Adding functionality to the plugin
----------------------------------

Now our example plugin will be very simple, we just want to add
new field to each entry called ``hello`` with value ``True``.

.. testcode::

   from flexget import plugin
   from flexget.event import event


   class Hello:
       def on_task_filter(self, task, config):
           for entry in task.entries:
               entry['hello'] = True

   @event('plugin.register')
   def register_plugin():
       plugin.register(Hello, 'hello', api_ver=2)

Adding more tests
-----------------

Let's supplement the testsuite with the test:

.. testcode::

   class TestHello:

       config = """
           tasks:
             test:
               mock:                 # let's use this plugin to create test data
                 - {title: 'foobar'} # we can omit url if we do not care about it, in this case mock will add random url
               hello: yes            # our plugin, no relevant configuration yet ...
       """

       def test_feature(self, execute_task):
         # run the task
         task = execute_task('test')
         for entry in task.entries:
             assert entry.get('hello') == True

Testing network-dependent code
==============================

Overview
--------

To ensure our test suite remains fast, deterministic, and capable of running in offline environments, we employ the `vcrpy`_ library to manage tests that rely on network I/O.
This system works by recording real HTTP interactions to a file (a "cassette") and replaying them on subsequent test runs.

This document outlines the standard procedure for creating and maintaining these tests.

Standard usage: the ``@pytest.mark.online`` decorator
-----------------------------------------------------

Any test function that initiates a network connection must be decorated with :term:`@pytest.mark.online`. ::

   import pytest

   @pytest.mark.online
   def test_api_fetch_data():
       # ... code that makes an HTTP request ...
       assert response.status_code == 200

This decorator instruments the test to use ``vcrpy`` to capture all outgoing network interactions and serialize them into a human-readable YAML file called a "cassette".

- On the first run, ``vcrpy`` will perform the actual network request and save the entire interaction (request and response) to a cassette file.
- On all subsequent runs, ``vcrpy`` intercepts any network call and replays the saved response from the cassette, bypassing the network entirely.

This methodology provides several key advantages:

*   Determinism: Tests are perfectly repeatable as they always receive the exact same response, eliminating flakiness from network or service variability.
*   Performance: Bypassing network latency drastically reduces test execution time.
*   Offline Execution: The entire test suite can be run without an active internet connection.

.. _`vcrpy`: https://vcrpy.readthedocs.io/

Workflow for new cassettes
--------------------------

When a new test decorated with ``@pytest.mark.online`` is executed, a corresponding cassette file is generated within the ``tests/cassettes/`` directory.
This file is considered an essential artifact of the test and must be committed to the repository.

To add a newly generated cassette, use the following command:

.. code:: console

   git add tests/cassettes/my_new_test_cassette.yaml

Advanced usage: record modes
----------------------------

During development, such as when an API endpoint changes or a test needs to be updated, you may need to force re-recording of a cassette.
Our test infrastructure, configured in ``conftest.py``, allows you to override the default recording behavior by setting the ``VCR_RECORD_MODE`` environment variable.

To run tests with a specific record mode, prefix the ``pytest`` command:

.. tab-set::
   :sync-group: os

   .. tab-item:: Unix
      :sync: Unix

      .. code:: console

         $ VCR_RECORD_MODE=all pytest tests/path/to/test_module.py

   .. tab-item:: Windows
      :sync: Windows

      .. code:: console

         $ powershell -c { $env:VCR_RECORD_MODE='all'; pytest tests/path/to/test_module.py }

The following modes are supported:

``once`` (Default)
    Records interactions if the cassette does not yet exist. If the cassette exists, it replays from it. If a new, unrecorded request is made, an error is raised.
``new_episodes``
    Replays existing interactions from the cassette and records any new interactions. Useful for incrementally adding calls to a test.
``all``
    Disables replay and forces re-recording of all interactions for the targeted tests, overwriting the existing cassette. Use this mode to update a cassette after an API has changed.
``none``
    Disables recording entirely. Only replays from the cassette. If any request is made that is not found in the cassette, an error is raised. This is useful for CI environments to guarantee no external network calls are made.

Provided fixtures and marks
===========================

To streamline testing for FlexGet, we provide a collection of custom ``pytest`` fixtures and marks.

This document covers the most common utilities. For an exhaustive list, refer to the fixtures defined
in ``/tests/conftest.py`` and the marks registered in ``pyproject.toml``.

Fixtures
--------

.. glossary::

   ``execute_task(task_name)``
     Use this fixture to execute a FlexGet task within a test.

Marks
-----

.. glossary::

   ``@pytest.mark.online``
     Tests that make external network requests must use this mark. It integrates ``vcrpy`` to capture all network interactions into YAML files called "cassettes". Subsequent test runs then replay these interactions from the cassette, eliminating the need for a live network connection. This approach guarantees deterministic test outcomes, improves execution speed, and enables offline testing.

   ``@pytest.mark.filecopy(source, destination)``
     Copies a file or directory before a test runs. Both ``source`` and ``destination`` can be a ``str`` or ``pathlib.Path`` object.

   ``@pytest.mark.require_optional_deps``
     Apply this mark to tests that rely on optional dependencies (as defined under the ``all`` key in ``pyproject.toml``). This ensures the CI pipeline installs these dependencies before executing the test.

Mock input
==========

Using special input plugin called ``mock`` to produce almost any kind of
entries in a task. This is probably one of the best ways to test things.

Example:

.. code:: yaml

   tasks:
     my-test:
       mock:
         - {title: 'title of test', description: 'foobar'}
       my_custom_plugin:
         do_stuff: yes

This will generate one entry in the task, notice that entry has two mandatory
fields ``title`` and ``url``. If ``url`` is not defined the mock plugin will
generate random url for localhost. The ``description`` filed is just arbitrary
field that we define in here. We can define any kind of basic text, number, list
or dictionary fields in here.

Controlling plugin behavior in tests with ``task.options``
==========================================================

You can leverage the ``task.options`` dictionary to alter a plugin's behavior during test
execution, which is particularly useful for debugging.

Plugin implementation
---------------------

The plugin checks for a specific option to decide whether to suppress an exception.
In a normal run, it logs the error and continues. In a test run, it re-raises the
exception so the test framework can catch it and fail the test correctly.

::

   def on_task_output(self, task, config):
       try:
           # ... business logic ...
       except Exception:
           logger.exception('Found an error')
           # If running under a test, re-raise the exception for clearer failure reports.
           if task.options.test:
               raise

Testing code
------------

The test case passes an ``options`` dictionary when calling ``execute_task``.
This dictionary becomes accessible as ``task.options`` within the plugin.

::

   def test_something(self, execute_task):
       # Setting {'test': True} enables the special test-mode behavior in the plugin.
       execute_task('task-name', options={'test': True})

The key ``test`` is just an example.
You can use any key-value pair (e.g., ``{'is_testing': True}``) as a flag, as long as
your plugin and test code are consistent. The core idea is to pass a signal from the
test runner into the plugin's execution context.

Code coverage
=============

We enforce two code coverage policies on every pull request:

- ``codecov/patch``: Mandates 100% test coverage for all changed code.
- ``codecov/project``: Prevents any drop in the overall project coverage.

Inject
======

The subcommand ``inject`` is very useful during development, assuming previous
example configuration you could try with some other title simply running following.

Example:

.. code:: console

  $ flexget inject "another test title"

The ``inject`` will disable any other inputs in the task. It is possible to set
arbitrary fields through inject much like with mock. See
`full documentation <https://flexget.com/en/CLI/inject>`__.

Commandline values
==================

The argument |--cli config|_ may be useful
if you need to try bunch of different values in the configuration file. It allows placing
variables in the configuration file.

.. |--cli config| replace:: ``--cli config``
.. _--cli config: https://flexget.com/Plugins/--cli-config

Example:

.. code:: yaml

   task:
     my-test:
       mock:
         - {title: foobar}
       regexp:
         accept:
           - $regexp


Run with command:

.. code:: console

  $ flexget execute --cli-config "regexp=foobar"
