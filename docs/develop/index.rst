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

Using `Poetry`_ is the easiest way to set up a development environment:

#. `Install Poetry`_
#. Git clone `our repository`_.
#. Run ``poetry install`` in the checkout directory to create a virtual environment
   and install Flexget in it.

.. _Poetry: https://python-poetry.org/
.. _Install Poetry: https://python-poetry.org/docs/#installation

For easier collaboration we recommend forking us on github and sending pull
request. Once we see any semi-serious input from a developer we will grant
write permissions to our central repository. You can also request this earlier
if you wish.

If you are new to Git there are several interactive tutorials you can try to get
you started including `try Git`_ and `Learn Git Branching`_.

.. _our repository: https://github.com/Flexget/Flexget
.. _try Git: https://try.github.io
.. _Learn Git Branching: https://pcottle.github.io/learnGitBranching/

Environment
-----------

Once you have done a ``poetry install``, you have a fully functional FlexGet in
a `virtual environment`_ in your clone directory. You can easily add or modify
existing plugins in here and it will not mess your other FlexGet instances in
any way. The commands in the documentation expect the virtual environment to be
activated. If you don't activate it you must run commands explicitly using
poetry E.g. ``flexget`` would be ``poetry run flexget``.

How to activate virtual environment::

  poetry shell


.. _virtual environment: https://python-poetry.org/docs/basic-usage#using-your-virtual-environment

Code quality
------------

Unit tests
~~~~~~~~~~

There are currently over 250 unit tests ensuring that existing functionality
is not accidentally broken. Additional requirements to run unit tests are
installed automatically during a poetry installation.::

We use the `pytest`_ framework for testing. Easiest way to run tests is just::

  pytest

Run single test file via py.test::

  pytest -v test_file.py

Run single test suite (class)::

  pytest -v test_file.py::TestClass

Run single test case from suite::

  pytest test_file.py::TestClass::test_method

Live example::

  pytest tests/test_seriesparser.py::TestSeriesParser::test_basic


Project has `GitHub Actions`_ set up, which will run all the tests on
PRs and the main development branch. Releases will be made automatically
daily if the tests are all passing.

Unit tests are not mandatory for a plugin to be included in the FlexGet
distribution but it makes maintaining our code trough project life and
refactoring so much easier. As such, contributions are much more likely
to be accepted if they are included.

.. _GitHub Actions: https://github.com/Flexget/Flexget/actions

Code Style
~~~~~~~~~~

All code should be formatted according to `Python PEP8`_ recommendations. With
the exception of line length limit at 79 characters. FlexGet uses 120 characters
instead. We use `black`_ and `isort`_ to enforce our code style. The easiest
way to run these tools, is to install our `pre-commit`_ hooks, which will run our
tools every time you do a git commit, and fix the style for you.

To install the pre-commit hooks::

  pre-commit install

.. _black: https://black.readthedocs.io/en/stable/
.. _isort: https://pycqa.github.io/isort/
.. _pre-commit: https://pre-commit.com/
.. _pytest: https://docs.pytest.org/en/latest/
.. _Python PEP8: http://www.python.org/dev/peps/pep-0008/
