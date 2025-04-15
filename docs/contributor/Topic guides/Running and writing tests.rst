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
<Installing additional testing dependencies>` must be installed.

To run all tests, simply execute:

.. code:: console

   $ uv run pytest

If you want to run tests in parallel to speed up the process, run:

.. code:: console

   $ uv run pytest -n logical --dist loadgroup

If you want to run a specific test within a module or run all tests in a class,
see `Specifying which tests to run <https://docs.pytest.org/en/stable/how-to/usage.html>`__.

.. note::
   If you don't want to prepend ``uv run`` to the ``pytest`` command, you can also choose to
   enter the virtual environment:

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

Example: Testing a plugin
=========================

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

Fixtures and marks we provide
=============================
To facilitate writing tests for FlexGet, we provide a set of fixtures and marks.
Some of these fixtures are also available as marks. Below are the most commonly used ones.
A complete list of fixtures can be found in ``/tests/conftest.py``, while all marks
are documented in ``pyproject.toml``.

Fixtures
--------

- For tests that require running a configuration, the ``execute_task(task name)`` fixture must be
  used. Usage has been demonstrated in the examples above.
- For tests necessitating network access, it is essential to use ``use_vcr`` fixture (equivalent to
  the ``@pytest.mark.online`` mark). This allows ``vcrpy`` to intercept and serialize network
  interactions into cassettes, enabling deterministic replay in subsequent test runs. By obviating
  the need for live network connectivity, this mechanism fortifies test stability and substantially
  enhances execution efficiency.

Marks
-----

- ``@pytest.mark.online`` is equivalent to the ``use_vcr`` fixture.
- For tests necessitating file duplication, one may leverage
  ``@pytest.mark.filecopy(source, destination)``, wherein ``source`` and ``destination`` may be
  instantiated as either ``str`` or ``Path``.
- For tests contingent upon auxiliary dependencies (enumerated under the ``plugin-test`` group in
  ``pyproject.toml``), it is imperative to annotate them with
  ``@pytest.mark.require_optional_deps`` to ensure their execution within the CI pipeline.

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
generate random url for localhost. The ``description`` filed is just arbitary
field that we define in here. We can define any kind of basic text, number, list
or dictionary fields in here.


Inject
======

The subcommand ``inject`` is very useful during development, assuming previous
example configuration you could try with some other title simply running following.

Example:

.. code:: console

  $ flexget inject "another test title"

The ``inject`` will disable any other inputs in the task. It is possible to set
arbitrary fields trough inject much like with mock. See
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
