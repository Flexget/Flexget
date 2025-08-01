.. image:: https://github.com/flexget/flexget/raw/develop/docs/_static/logo.png
   :align: center
   :target: https://flexget.com
   :height: 50

|

.. image:: https://img.shields.io/pypi/v/Flexget.svg
   :target: https://pypi.org/project/flexget/

.. image:: https://img.shields.io/docker/v/flexget/flexget?logo=docker&logoColor=aqua&label=docker%20image&color=aqua
   :target: https://hub.docker.com/r/flexget/flexget

.. image:: https://img.shields.io/pypi/pyversions/Flexget.svg
   :target: https://pypi.org/project/flexget/

.. image:: https://codecov.io/gh/Flexget/Flexget/graph/badge.svg
   :target: https://codecov.io/gh/Flexget/Flexget

..
   Commenting these out for now, as they seem to be broken.
   .. image:: https://api.codacy.com/project/badge/Grade/86bb847efe984c12948bdeccabcbccad
      :target: https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Grade

.. image:: https://github.com/Flexget/Flexget/actions/workflows/test.yml/badge.svg?branch=develop
   :target: https://github.com/Flexget/Flexget/actions/workflows/test.yml?query=branch%3Adevelop

.. image:: https://readthedocs.org/projects/flexget/badge/?version=latest
   :target: https://flexget.readthedocs.io/en/latest/

.. image:: http://isitmaintained.com/badge/resolution/Flexget/Flexget.svg
   :target: http://isitmaintained.com/project/Flexget/Flexget

.. image:: https://img.shields.io/discord/536690097056120833?label=discord
   :target: https://discord.gg/W6CQrJx

.. image:: https://img.shields.io/badge/Libera%20chat-%23flexget-orange
   :target: https://web.libera.chat/#flexget

`FlexGet`_ is a multipurpose automation tool for content like torrents, nzbs,
podcasts, comics, series, movies, etc. It can use different kinds of sources
like RSS-feeds, html pages, csv files, search engines and there are even
plugins for sites that do not provide any kind of useful feeds.

Example
=======
Flexget uses a `YAML`_ based configuration file.
The following example will look in the RSS feed in the link, will match any
item that match the series names and download it::

    tasks:
      tv:
        rss: http://example.com/torrents.xml
        series:
        - some series
        - another series
        download: /tvshows

There are numerous plugins that allow utilizing FlexGet in interesting ways
and more are being added continuously.

FlexGet is extremely useful in conjunction with applications which have watch
directory support or provide interface for external utilities like FlexGet.
To get a sense of the many things that can be done with FlexGet you can take
a look in our `cookbook`_.

.. _FlexGet: https://flexget.com

.. _YAML: http://www.yaml.org/

.. _cookbook: https://flexget.com/Cookbook


**ChangeLog:** https://flexget.com/ChangeLog

**Help:** https://github.com/Flexget/Flexget/discussions

**Chat:** https://flexget.com/Chat

**Bugs:** https://github.com/Flexget/Flexget/issues

**API reference** https://flexget.readthedocs.io/en/latest/api/flexget.html

Install
-------

FlexGet is installable via pip with the command::

   pip install flexget

For more detailed instructions see the `installation guide`_.

.. _installation guide: https://flexget.com/Install

How to contribute
-----------------------

Refer to `the contributor guide <https://flexget.readthedocs.io/en/latest/contributor/index.html>`__.

If you don't want to use virtualenv there's ``flexget_vanilla.py`` file which
can be used to run FlexGet without virtualenv, note that you will need to
install all required dependencies yourself.
