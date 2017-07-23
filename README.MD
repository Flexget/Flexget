# FlexGet

[![travis](https://api.travis-ci.org/Flexget/Flexget.png?branch=master)](https://travis-ci.org/Flexget/Flexget)
[![pypi](https://img.shields.io/pypi/v/Flexget.svg)](https://pypi.python.org/pypi/Flexget)
[![downloads](https://img.shields.io/pypi/dm/Flexget.svg)](https://pypi.python.org/pypi/Flexget)
[![codacy grade](https://api.codacy.com/project/badge/Grade/81e8ae42c7544dc48853102b1b7f88d5)](https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Grade)
[![codacy coverage](https://api.codacy.com/project/badge/Coverage/81e8ae42c7544dc48853102b1b7f88d5)](https://www.codacy.com/app/Flexget/Flexget?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Flexget/Flexget&amp;utm_campaign=Badge_Coverage)
[![gitter](https://img.shields.io/gitter/room/nwjs/nw.js.svg)](https://gitter.im/Flexget/Flexget)
[![isitmaintained.com](http://isitmaintained.com/badge/resolution/Flexget/Flexget.svg)](http://isitmaintained.com/project/Flexget/Flexget)

[FlexGet](https://flexget.com) is a multipurpose automation tool for content like torrents, nzbs, podcasts, comics, series, movies, etc. It can use different kinds of sources like RSS-feeds, html pages, csv files, search engines, and there are even plugins for sites that do not provide any kind of useful feeds.

## Example

Flexget uses a [YAML](http://www.yaml.org/)-based configuration file.
The following example will look in the RSS feed in the link, will match any item that match the listed series names and download it:
```yaml
tasks:
  tv_task:
    rss: http://example.com/torrents.xml
    series:
    - some series
    - another series
    download: /tvshows
```

There are numerous plugins that allow utilizing FlexGet in interesting ways and more are being added continuously.

FlexGet is extremely useful in conjunction with applications which have watch directory support or provide interface for external utilities like FlexGet.

To get a sense of the many things that can be done with FlexGet you can take a look in our [Cookbook](https://flexget.com/Cookbook)


**ChangeLog:** https://flexget.com/ChangeLog

**Help:** https://discuss.flexget.com/

**Chat:** http://webchat.freenode.net/?channels=#flexget or https://gitter.im/Flexget/Flexget

**Bugs:** https://github.com/Flexget/Flexget/issues

### Feature requests
[![Feature Requests](http://feathub.com/Flexget/Flexget?format=svg)](http://feathub.com/Flexget/Flexget)

## Base system requirements

FlexGet requires Python v2.7, 3.3, 3.4, or 3.5. It *may* run on 3.6 but we do not support that version at this time.

## Install
FlexGet is installable via pip with the command:

    pip install flexget

For more detailed instructions see the [installation guide](https://flexget.com/Install).

## Install via git checkout

Clone the repo with this command:

    git clone https://github.com/Flexget/Flexget.git ~/flexget-dev

Detailed instructions are available on [flexget.com](https://flexget.com/GitHubInstall).

