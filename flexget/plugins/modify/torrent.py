import logging
from flexget.plugin import register_plugin, priority, PluginError
# TORRENT_RE is redundant by now, but keep it here, in case someone was crazy enough to import it
from flexget.utils.bittorrent import Torrent, is_torrent_file, TORRENT_RE 
import os

log = logging.getLogger('modif_torrent')


class TorrentFilename(object):
    """
        Makes sure that entries containing torrent-file have .torrent
        extension. This is enabled always by default (builtins).
    """
    TORRENT_PRIO = 255

    @priority(TORRENT_PRIO)
    def on_feed_modify(self, feed):
        for entry in feed.entries:
            # skip if entry does not have file assigned
            if not 'file' in entry:
                log.debugall('%s doesn\'t have a file associated' % entry['title'])
                continue
            if not os.path.exists(entry['file']):
                raise PluginError('File %s does not exists' % entry['file'])
            if os.path.getsize(entry['file']) == 0:
                raise PluginError('File %s is 0 bytes in size' % entry['file'])

            if not is_torrent_file(entry['file']):
                continue
            log.debug('%s seems to be a torrent' % entry['title'])

            # create torrent object from torrent
            try:
                f = open(entry['file'], 'rb')
                # NOTE: this reads entire file into memory, but we're pretty sure it's
                # a small torrent file since it starts with TORRENT_RE
                data = f.read()
                f.close()

                if 'content-length' in entry:
                    if len(data) != entry['content-length']:
                        feed.fail(entry, 'Torrent file length doesn\'t match to the one reported by the server')
                        self.purge(entry)
                        continue

                # construct torrent object
                try:
                    torrent = Torrent(data)
                except SyntaxError, e:
                    feed.fail(entry, '%s - Torrent could not be parsed' % e.message)
                    self.purge(entry)
                    continue

                entry['torrent'] = torrent
                entry['torrent_info_hash'] = torrent.get_info_hash()
                # if we do not have good filename (by download plugin)
                # for this entry, try to generate one from torrent content
                if entry.get('filename'):
                    if not entry['filename'].lower().endswith('.torrent'):
                        # filename present but without .torrent extension, add it
                        entry['filename'] = entry['filename'] + '.torrent'
                else:
                    # generate filename from torrent or fall back to title plus extension
                    entry['filename'] = self.make_filename(torrent, entry)
            except Exception, e:
                log.exception(e)

    @priority(TORRENT_PRIO)
    def on_feed_output(self, feed):
        for entry in feed.entries:
            if 'torrent' in entry:
                if entry['torrent'].modified:
                    # re-write data into a file
                    log.debug('Writing modified torrent file for %s' % entry['title'])
                    f = open(entry['file'], 'wb+')
                    f.write(entry['torrent'].encode())
                    f.close()

    def make_filename(self, torrent, entry):
        """Build a filename for this torrent"""

        title = entry['title']
        files = torrent.get_filelist()
        if len(files) == 1:
            # single file, if filename is longer than title use it
            fn = files[0]['name']
            if len(fn) > len(title):
                title = fn[:fn.rfind('.')]

        # neatify title
        title = title.replace('/', '_')
        title = title.replace(' ', '_')
        title = title.replace('\u200b', '')

        # title = title.encode('iso8859-1', 'ignore') # Damn \u200b -character, how I loathe thee
        # TODO: replace only zero width spaces, leave unicode alone?

        fn = '%s.torrent' % title
        log.debug('make_filename made %s' % fn)
        return fn

    def purge(self, entry):
        import os
        if os.path.exists(entry['file']):
            log.debug('removing temp file %s from %s' % (entry['file'], entry['title']))
            os.remove(entry['file'])
        del(entry['file'])


register_plugin(TorrentFilename, 'torrent', builtin=True)
