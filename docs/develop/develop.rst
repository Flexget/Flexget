Develop
=======

We welcome all new developers and contributors with very friendly community.
Join #FlexGet @ freenode.

How do I get started?
---------------------

Set up development environment, which is basically just two steps.

#. `GIT clone`_ our repository.
#. Run ``bootstrap.py`` with Python 2.6.x - 2.7.x.

For easier collaboration we recommend forking us on github and sending pull
request. Once we see any semi-serious input from a developer we will grant
write permissions to our central repository. You can also request this earlier
if you wish.

.. _GIT clone: https://github.com/Flexget/Flexget

Environment
-----------

Once you have bootstrapped the environment you have fully functional FlexGet in
a `virtual environment`_ in your clone directory. You can easily add or modify
existing plugins in here and it will not mess your other FlexGet instances in
any way. The commands in the documentation expect the virtual environment to be
activated. If you don't activate it you must run commands explicitly from under
environment ``bin`` directory or ``scripts`` in windows. E.g. ``flexget`` would
be ``bin/flexget`` (at project root) in unactivated `virtual environment`_.

FlexGet project uses `paver`_ to provide development related utilities and tasks.
Run ``paver --help`` to see what commands are available. Some of these will
be mentioned later.

.. _virtual environment: https://pypi.python.org/pypi/virtualenv
.. _paver: http://paver.github.io/paver/

Code quality
------------

Unit tests
~~~~~~~~~~

There are currently over 250 unit tests ensuring that existing functionality
is not accidentally broken.

Easiest way to run tests is trough paver::

  paver test

By default no online tests are executed, these can be enabled with ``--online``
argument. There are other ways to run the tests as well, more specifically
we use `nose`_ framework.

Unit tests are not mandatory for a plugin to be included in the FlexGet
distribution but it makes maintaining our code trough project life and
refactoring so much easier.

Code Style
~~~~~~~~~~

All code should be formatted according to `Python PEP8`_ recommendations. With
the exception of line length limit at 79 characters. FlexGet uses 120 characters
instead.

To run PEP8 checker::

  paver pep8

We do have some violations in our codebase, but new code should not add any.

.. _nose: https://nose.readthedocs.org/
.. _Python PEP8: http://www.python.org/dev/peps/pep-0008/