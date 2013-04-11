import logging
import re
import os
import sys

from flexget import plugin
from flexget import validator

log = logging.getLogger('rtorrent_magnet')
pat = re.compile('xt=urn:btih:([^&/]+)')


class PluginRtorrentMagnet(object):
    """
    Process Magnet URI's into rtorrent compatible torrent files

    Magnet URI's will look somethign like this:

    magnet:?xt=urn:btih:190F1ABAED7AE7252735A811149753AA83E34309&dn=URL+Escaped+Torrent+Name

    rTorrent would expect to see something like meta-URL_Escaped_Torrent_Name.torrent

    The torrent file must also contain the text:

    d10:magnet-uri88:xt=urn:btih:190F1ABAED7AE7252735A811149753AA83E34309&dn=URL+Escaped+Torrent+Namee

    This plugin will check if a download URL is a magnet link, and then create the appropriate torrent file.

    Example:
      rtorrent_magnet: ~/torrents/
    """

    def write_torrent_file(self, task, entry):
        path = os.path.join(
            entry['path'],
            'meta-%s.torrent' % entry['title'].encode(sys.getfilesystemencoding(), 'replace')
        )
        path = os.path.expanduser(path)
        log.info('Writing rTorrent Magnet File: %s', path)

        if task.manager.options.test:
            log.info('Would write: d10:magnet-uri%d:%se' % (entry['url'].__len__(), entry['url']))
        else:
            with open(path, 'w') as f:
                f.write('d10:magnet-uri%d:%se' % (entry['url'].__len__(), entry['url']))
            f.closed

        entry['output'] = path

    def validator(self):
        root = validator.factory()
        root.accept('path', allow_replacement=True)
        return root

    @plugin.priority(0)
    def on_task_output(self, task, config):

        for entry in task.accepted:
            if 'output' in entry:
                log.debug('Ignoring, %s already has an output file: %s' % (entry['title'], entry['output']))
                continue

            urls = entry.get('urls', [entry['url']])

            for url in urls:
                if url.startswith('magnet:'):
                    log.debug('Magnet URI detected for url %s (%s)' % (url, entry['title']))

                    m = pat.search(url)
                    if m:
                        entry['url'] = url
                        entry['path'] = entry.get('path', config)
                        entry['hash'] = m.groups()[0]

                        log.debug('Magnet Hash Detected: %s' % entry['hash'])

                        self.write_torrent_file(task, entry)

                        break
                    else:
                        log.warning('Unrecognized Magnet URI Format: %s', url)

plugin.register_plugin(PluginRtorrentMagnet, 'rtorrent_magnet', api_ver=2)
