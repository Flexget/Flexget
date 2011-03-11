import logging
import httplib
from flexget.plugin import priority, register_plugin

log = logging.getLogger('kat_patch')
triggered = False


def monkeypatched_read_chunked(self, amt):
    from httplib import _UNKNOWN

    assert self.chunked != _UNKNOWN
    chunk_left = self.chunk_left
    value = []
    while True:
        if chunk_left is None:
            line = self.fp.readline()
            i = line.find(';')
            if i >= 0:
                line = line[:i] # strip chunk-extensions
            try:
                chunk_left = int(line, 16)
            except ValueError:
                # close the connection as protocol synchronisation is
                # probably lost
                self.close()
                log.warning('IncompleteRead error (expected)')
                global triggered
                triggered = True
                break
                #raise IncompleteRead(''.join(value))
            if chunk_left == 0:
                break
        if amt is None:
            value.append(self._safe_read(chunk_left))
        elif amt < chunk_left:
            value.append(self._safe_read(amt))
            self.chunk_left = chunk_left - amt
            return ''.join(value)
        elif amt == chunk_left:
            value.append(self._safe_read(amt))
            self._safe_read(2)  # toss the CRLF at the end of the chunk
            self.chunk_left = None
            return ''.join(value)
        else:
            value.append(self._safe_read(chunk_left))
            amt -= chunk_left

        # we read the whole chunk, get another
        self._safe_read(2)      # toss the CRLF at the end of the chunk
        chunk_left = None

    # read and discard trailer up to the CRLF terminator
    ### note: we shouldn't have any trailers!
    while True:
        if not self.fp:
            break
        line = self.fp.readline()
        if not line:
            # a vanishingly small number of sites EOF without
            # sending the trailer
            break
        if line == '\r\n':
            break
    # we read everything; close the "file"
    self.close()

    return ''.join(value)


class MonkeypatchKickassTorrents(object):

    """
    A hack to get KickassTorrents to work
    """

    def __init__(self):
        self.patched = False
        self.original = httplib.HTTPResponse._read_chunked

    @priority(-255)
    def on_feed_urlrewrite(self, feed):
        for entry in feed.entries:
            if 'kickasstorrent' in entry['url'] and not self.patched:
                log.info('Monkeypatching httplib to overcome kickasstorrents failure')
                httplib.HTTPResponse._read_chunked = monkeypatched_read_chunked
                self.patched = True
                break

    def on_feed_exit(self, feed):
        if self.patched:
            if not triggered and feed.accepted:
                log.info('Looks like kickasstorrents monkeypatch was not needed, please notify FlexGet developers')
            log.info('Removing monkeypatch')
            httplib.HTTPResponse._read_chunked = self.original
            self.patched = False

    on_feed_abort = on_feed_exit

register_plugin(MonkeypatchKickassTorrents, 'ka_patch', builtin=True)
