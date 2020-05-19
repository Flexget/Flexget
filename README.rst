FlexGet
=======
.. image:: https://github.com/Flexget/Flexget/workflows/Main%20Workflow/badge.svg?branch=develop&event=schedule
    :target: https://github.com/Flexget/Flexget/actions?query=workflow%3A%22Main+Workflow%22+branch%3Adevelop+event%3Aschedule

.. image:: https://img.shields.io/pypi/v/Flexget.svg
    :target: https://pypi.python.org/pypi/Flexget

.. image:: https://api.codacy.com/project/badge/Grade/86bb847efe984c12948bdeccabcbccad
    :target: https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Grade

.. image:: https://api.codacy.com/project/badge/Coverage/86bb847efe984c12948bdeccabcbccad
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
The following example will look in the RSS feed in the link, will match any item that match the series names and download it::

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

**Chat:** https://flexget.com/Chat

**Bugs:** https://github.com/Flexget/Flexget/issues

Install
-------

FlexGet is installable via pip with the command::

    pip install flexget

For more detailed instructions see the `installation guide`_.

.. _installation guide: https://flexget.com/Install

Feature requests
----------------
.. image:: http://feathub.com/Flexget/Flexget?format=svg
   :target: http://feathub.com/Flexget/Flexget

How to use GIT checkout
-----------------------

Check that you have Python 3.6 or newer available with command ``python -V``.

In some environments newer python might be available under another name like
'python3.6' or 'python3' in which case you need to use that one instead of
plain 'python'.

To start using FlexGet from this directory::

    python3 -m venv .

This will initialize python virtualenv. This doesn't need to be directly in
your checkout directory, but these instructions assume that's where it is.

On some linux distributions (eg. debian, ubuntu) venv module is not included with
python and this fails. Please install `python3-virtualenv` package and retry
(or use the separate `virtualenv`_ python package).

.. _virtualenv: https://pypi.python.org/pypi/virtualenv

Upgrading pip to latest version is highly advisable and can de done with::

    bin/pip install --upgrade pip

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
