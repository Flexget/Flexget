from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('priv_torrents')


class FilterPrivateTorrents(object):
    """How to handle private torrents.

    private_torrents: yes|no

    Example::

      private_torrents: no

    This would reject all torrent entries with private flag.

    Example::

      private_torrents: yes

    This would reject all public torrents.

    Non-torrent content is not interviened.
    """

    schema = {'type': 'boolean'}

    @plugin.priority(127)
    def on_task_modify(self, task, config):
        private_torrents = config

        for entry in task.accepted:
            if 'torrent' not in entry:
                log.debug('`%s` is not a torrent' % entry['title'])
                continue
            private = entry['torrent'].private

            if not private_torrents and private:
                entry.reject('torrent is marked as private', remember=True)
            elif private_torrents and not private:
                entry.reject('public torrent', remember=True)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterPrivateTorrents, 'private_torrents', api_ver=2)
