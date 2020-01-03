import os

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.bittorrent import Torrent, is_torrent_file

logger = logger.bind(name='modif_torrent')


class TorrentFilename:
    """
        Makes sure that entries containing torrent-file have .torrent
        extension. This is enabled always by default (builtins).
    """

    TORRENT_PRIO = 255

    @plugin.priority(TORRENT_PRIO)
    def on_task_modify(self, task, config):
        # Only scan through accepted entries, as the file must have been downloaded in order to parse anything
        for entry in task.accepted:
            # skip if entry does not have file assigned
            if 'file' not in entry:
                logger.trace("{} doesn't have a file associated", entry['title'])
                continue
            if not os.path.exists(entry['file']):
                logger.debug('File {} does not exist', entry['file'])
                continue
            if os.path.getsize(entry['file']) == 0:
                logger.debug('File {} is 0 bytes in size', entry['file'])
                continue
            if not is_torrent_file(entry['file']):
                continue
            logger.debug('{} seems to be a torrent', entry['title'])

            # create torrent object from torrent
            try:
                with open(entry['file'], 'rb') as f:
                    # NOTE: this reads entire file into memory, but we're pretty sure it's
                    # a small torrent file since it starts with TORRENT_RE
                    data = f.read()

                if 'content-length' in entry:
                    if len(data) != entry['content-length']:
                        entry.fail(
                            'Torrent file length doesn\'t match to the one reported by the server'
                        )
                        self.purge(entry)
                        continue

                # construct torrent object
                try:
                    torrent = Torrent(data)
                except SyntaxError as e:
                    entry.fail('%s - broken or invalid torrent file received' % e.args[0])
                    self.purge(entry)
                    continue

                logger.trace('working on torrent {}', torrent)
                entry['torrent'] = torrent
                entry['torrent_info_hash'] = torrent.info_hash
                # if we do not have good filename (by download plugin)
                # for this entry, try to generate one from torrent content
                if entry.get('filename'):
                    if not entry['filename'].lower().endswith('.torrent'):
                        # filename present but without .torrent extension, add it
                        entry['filename'] += '.torrent'
                else:
                    # generate filename from torrent or fall back to title plus extension
                    entry['filename'] = self.make_filename(torrent, entry)
            except Exception as e:
                logger.exception(e)

    @plugin.priority(TORRENT_PRIO)
    def on_task_output(self, task, config):
        for entry in task.entries:
            if 'torrent' in entry:
                if entry['torrent'].modified:
                    # re-write data into a file
                    logger.debug('Writing modified torrent file for {}', entry['title'])
                    with open(entry['file'], 'wb+') as f:
                        f.write(entry['torrent'].encode())

    def make_filename(self, torrent, entry):
        """Build a filename for this torrent"""

        title = entry['title']
        files = torrent.get_filelist()
        if len(files) == 1:
            # single file, if filename is longer than title use it
            fn = files[0]['name']
            if len(fn) > len(title):
                title = fn[: fn.rfind('.')]

        # neatify title
        title = title.replace('/', '_')
        title = title.replace(' ', '_')
        title = title.replace('\u200b', '')

        # title = title.encode('iso8859-1', 'ignore') # Damn \u200b -character, how I loathe thee
        # TODO: replace only zero width spaces, leave unicode alone?

        fn = '%s.torrent' % title
        logger.debug('make_filename made {}', fn)
        return fn

    def purge(self, entry):
        if os.path.exists(entry['file']):
            logger.debug('removing temp file {} from {}', entry['file'], entry['title'])
            os.remove(entry['file'])
        del entry['file']


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentFilename, 'torrent', builtin=True, api_ver=2)
