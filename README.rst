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


Install
-------

FlexGet is installable via pip with the command::

    pip install flexget

For more detailed instructions see the `installation guide`_.

.. _installation guide: http://flexget.com/wiki/Install


How to use GIT checkout
-----------------------

Check that you have Python 2.6 - 2.7 available with command ``python -V``.

In some environments newer (or older, if your distro is on python 3,) python
might be available under another name like 'python26' or 'python2.7' in which
case you need to use that one instead of plain 'python'.

To start using FlexGet from this directory, run the following commands::

    python bootstrap.py

This will initialize python virtualenv and install all required dependencies
in it.

If you need deluge or transmission libraries from system wide python use::

    python bootstrap.py --system-site-packages

After that FlexGet is usable via ``<checkout directory>/bin/flexget``. Verify
installation by running::

    bin/flexget -V

You may also place the configuration files in ``~/.flexget`` (Unix, Mac OS X)
or ``C:\Documents and Setting\<username>\flexget`` (Windows).

If you don't want to use virtualenv there's ``flexget_vanilla.py`` file which
can be used to run FlexGet without bootstrapping, note that you will need to
install all required dependencies yourself.
