Introduction
============

We welcome all new developers and contributors with very friendly community.
Join #FlexGet @ freenode.

Technologies used
-----------------

List of external libraries and utilities. As for new libraries, we require that all of them are
installable on Windows trough ``pip``. This will exclude things that require compilers like LXML.

Core
~~~~

* SQLAlchemy
* BeautifulSoup
* Feedparser
* Python-Requests
* PyNBZ
* Jinja2
* PyYaml
* jsonschema
* Some smaller misc libraries

HTTPServer
~~~~~~~~~~

* Flask
* Jinja2
* CherryPy

CherryPy is only used for WSGI server.

How do I get started?
---------------------

Set up development environment, which is basically just three steps:

#. Git clone `our repository`_.
#. Create a virtual environment in your clone dir (``python3 -m venv <venv-dir>``).
#. Run ``<venv-dir>/bin/pip install -e .`` from your checkout directory.

For easier collaboration we recommend forking us on github and sending pull
request. Once we see any semi-serious input from a developer we will grant
write permissions to our central repository. You can also request this earlier
if you wish.

If you are new to Git there are several interactive tutorials you can try to get
you started including `try Git`_ and `Learn Git Branching`_.

.. _our repository: https://github.com/Flexget/Flexget
.. _try Git: http://try.github.io
.. _Learn Git Branching: http://pcottle.github.io/learnGitBranching/

Environment
-----------

Once you have bootstrapped the environment you have fully functional FlexGet in
a `virtual environment`_ in your clone directory. You can easily add or modify
existing plugins in here and it will not mess your other FlexGet instances in
any way. The commands in the documentation expect the virtual environment to be
activated. If you don't activate it you must run commands explicitly from the
environment's ``bin`` directory or ``scripts`` in windows. E.g. ``flexget`` would
be ``bin/flexget`` relative to the root of the unactivated `virtual environment`_.

How to activate virtual environment under linux::

  source bin/activate


.. _virtual environment: https://docs.python.org/3/library/venv.html

Code quality
------------

Unit tests
~~~~~~~~~~

There are currently over 250 unit tests ensuring that existing functionality
is not accidentally broken. Unit tests can be invoked with the installation
of additional requirements::

  pip install -r dev-requirements.txt

We use the `py.test`_ framework for testing. Easiest way to run tests is just::

  py.test

Run single test file via py.test::

  py.test -v test_file.py

Run single test suite (class)::

  py.test -v test_file.py::TestClass

Run single test case from suite::

  py.test test_file.py::TestClass::test_method

Live example::

  py.test tests/test_seriesparser.py::TestSeriesParser::test_basic


Project has `Jenkins CI server`_ which polls master branch and makes runs tests
and makes new build if they pass.

Unit tests are not mandatory for a plugin to be included in the FlexGet
distribution but it makes maintaining our code trough project life and
refactoring so much easier.

.. _Jenkins CI server: http://ci.flexget.com

Code Style
~~~~~~~~~~

All code should be formatted according to `Python PEP8`_ recommendations. With
the exception of line length limit at 79 characters. FlexGet uses 120 characters
instead.

To run PEP8 checker::

  flake8

We do have some violations in our codebase, but new code should not add any.

.. _py.test: https://pytest.org/latest/
.. _Python PEP8: http://www.python.org/dev/peps/pep-0008/
