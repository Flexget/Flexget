FlexGet
=======

`FlexGet`_ is a multipurpose automation tool for content like torrents, nzbs,
podcasts, comics, series, movies, etc. It can use different kinds of sources
like RSS-feeds, html pages, csv files, search engines and there are even
plugins for sites that do not provide any kind of useful feeds.

There are numerous plugins that allow utilizing FlexGet in interesting ways
and more are being added continuously.

FlexGet is extremely useful in conjunction with applications which have watch
directory support or provide interface for external utilities like FlexGet.

.. _FlexGet: http://flexget.com

.. image:: https://api.travis-ci.org/lildadou/Flexget.png?branch=music_snep
    :target: https://travis-ci.org/lildadou/Flexget

.. image:: https://img.shields.io/pypi/v/Flexget.svg
    :target: https://pypi.python.org/pypi/Flexget

.. image:: https://img.shields.io/pypi/dm/Flexget.svg
    :target: https://pypi.python.org/pypi/Flexget

.. image:: https://api.codacy.com/project/badge/Grade/81e8ae42c7544dc48853102b1b7f88d5
    :target: https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Grade

.. image:: https://api.codacy.com/project/badge/Coverage/81e8ae42c7544dc48853102b1b7f88d5
    :target: https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Coverage

.. image:: https://badges.gitter.im/Flexget/Flexget.svg
    :alt: Join the chat at https://gitter.im/Flexget/Flexget
    :target: https://gitter.im/Flexget/Flexget?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
    
.. image:: http://isitmaintained.com/badge/resolution/Flexget/Flexget.svg
    :target: http://isitmaintained.com/project/Flexget/Flexget


**Help:** http://discuss.flexget.com/

**Chat:** http://webchat.freenode.net/?channels=#flexget or https://gitter.im/Flexget/Flexget

**Bugs:** https://github.com/Flexget/Flexget/issues

Install
-------

FlexGet is installable via pip with the command::

    pip install flexget

For more detailed instructions see the `installation guide`_.

.. _installation guide: http://flexget.com/Install

How to use GIT checkout
-----------------------

Check that you have Python 2.7 / 3.3 or newer available with command ``python -V``.

In some environments newer python might be available under another name like 
'python2.7' or 'python3' in which case you need to use that one instead of 
plain 'python'.

To start using FlexGet from this directory:

First, install (a recent version of) the `virtualenv`_ package to your system.

.. _virtualenv: https://pypi.python.org/pypi/virtualenv

Now, in your checkout directory, run::

    virtualenv .

Or, if you need deluge or transmission libraries from system wide python use::

    virtualenv --system-site-packages .

This will initialize python virtualenv. This doesn't need to be directly in
your checkout directory, but these instructions assume that's where it is.

Next we need to install dependencies and FlexGet itself, this can be done simply::

    bin/pip install -e .

This does an editable (`-e`) development install of the current directory (`.`).

After that FlexGet is usable via ``<checkout directory>/bin/flexget``. Verify
installation by running::

    bin/flexget -V

You may place the config file in your checkout directory, or in ``~/.flexget``
(Unix, Mac OS X) or ``C:\Documents and Setting\<username>\flexget`` (Windows).

If you don't want to use virtualenv there's ``flexget_vanilla.py`` file which
can be used to run FlexGet without virtualenv, note that you will need to
install all required dependencies yourself.

Install using Docker (Linux only)
---------------------------------

Docker can be used to install and run FlexGet::

    docker run -it -v /home/<username>/.flexget:/root/.flexget --rm toilal/flexget
