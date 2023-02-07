import os
import re

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='rtorrent_magnet')
pat = re.compile('xt=urn:btih:([^&/]+)')


class PluginRtorrentMagnet:
    """
    Process Magnet URI's into rtorrent compatible torrent files

    Magnet URI's will look something like this:

    magnet:?xt=urn:btih:190F1ABAED7AE7252735A811149753AA83E34309&dn=URL+Escaped+Torrent+Name

    rTorrent would expect to see something like meta-URL_Escaped_Torrent_Name.torrent

    The torrent file must also contain the text:

    d10:magnet-uri88:xt=urn:btih:190F1ABAED7AE7252735A811149753AA83E34309&dn=URL+Escaped+Torrent+Namee

    This plugin will check if a download URL is a magnet link, and then create the appropriate torrent file.

    Example:
      rtorrent_magnet: ~/torrents/
    """

    schema = {'type': 'string', 'format': 'path'}

    def write_torrent_file(self, task, entry, path):
        path = os.path.join(path, 'meta-%s.torrent' % entry['title'])
        path = os.path.expanduser(path)

        if task.options.test:
            logger.info('Would write: {}', path)
        else:
            logger.info('Writing rTorrent Magnet File: {}', path)
            with open(path, 'w') as f:
                f.write('d10:magnet-uri%d:%se' % (len(entry['url']), entry['url']))
        entry['output'] = path

    # Run after download plugin to only pick up entries it did not already handle
    @plugin.priority(0)
    def on_task_output(self, task, config):
        for entry in task.accepted:
            if 'output' in entry:
                logger.debug(
                    'Ignoring, {} already has an output file: {}', entry['title'], entry['output']
                )
                continue

            for url in entry.get('urls', [entry['url']]):
                if url.startswith('magnet:'):
                    logger.debug('Magnet URI detected for url {} ({})', url, entry['title'])
                    if pat.search(url):
                        self.write_torrent_file(task, entry, entry.get('path', config))
                        break
                    else:
                        logger.warning('Unrecognized Magnet URI Format: {}', url)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginRtorrentMagnet, 'rtorrent_magnet', api_ver=2)
