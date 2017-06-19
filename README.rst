FlexGet
=======
.. image:: https://api.travis-ci.org/Flexget/Flexget.png?branch=master
    :target: https://travis-ci.org/Flexget/Flexget

.. image:: https://img.shields.io/pypi/v/Flexget.svg
    :target: https://pypi.python.org/pypi/Flexget

.. image:: https://img.shields.io/pypi/dm/Flexget.svg
    :target: https://pypi.python.org/pypi/Flexget

.. image:: https://api.codacy.com/project/badge/Grade/81e8ae42c7544dc48853102b1b7f88d5
    :target: https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Grade

.. image:: https://api.codacy.com/project/badge/Coverage/81e8ae42c7544dc48853102b1b7f88d5
    :target: https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Coverage

.. image:: https://img.shields.io/gitter/room/nwjs/nw.js.svg
    :target: https://gitter.im/Flexget/Flexget

.. image:: http://isitmaintained.com/badge/resolution/Flexget/Flexget.svg
    :target: http://isitmaintained.com/project/Flexget/Flexget

`FlexGet`_ is a multipurpose automation tool for content like torrents, nzbs,
podcasts, comics, series, movies, etc. It can use different kinds of sources
like RSS-feeds, html pages, csv files, search engines and there are even
plugins for sites that do not provide any kind of useful feeds.

Example
=======
Flexget uses a `YAML`_ based configuration file.
The following example will look in the RSS feed in the link, will match any item that match the listes series names and download it::

    tasks:
      tv_task:
        rss: http://example.com/torrents.xml
        series:
        - some series
        - another series
        download: /tvshows

There are numerous plugins that allow utilizing FlexGet in interesting ways
and more are being added continuously.

FlexGet is extremely useful in conjunction with applications which have watch
directory support or provide interface for external utilities like FlexGet.
To get a sense of the many things that can be done with FlexGet you can take a look in our `cookbook`_.

.. _FlexGet: https://flexget.com

.. _YAML: http://www.yaml.org/

.. _cookbook: https://flexget.com/Cookbook


**ChangeLog:** https://flexget.com/ChangeLog

**Help:** https://discuss.flexget.com/

**Chat:** http://webchat.freenode.net/?channels=#flexget or https://gitter.im/Flexget/Flexget

**Bugs:** https://github.com/Flexget/Flexget/issues

Install
-------

FlexGet is installable via pip with the command::

    pip install flexget

For more detailed instructions see the `installation guide`_.

.. _installation guide: https://flexget.com/Install

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

