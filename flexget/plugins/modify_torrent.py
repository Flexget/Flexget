import re
import logging
from flexget.plugin import *

log = logging.getLogger('modif_torrent')

# Torrent decoding is a short fragment from effbot.org. Site copyright says:
# Test scripts and other short code fragments can be considered as being in the public domain.

TORRENT_RE = re.compile(r'^d\d{1,3}:')


class Torrent(object):
    """Represents a torrent"""

    def __init__(self, content):
        """Accepts torrent file as string"""

        self.encode_func = {}
        self.encode_func[type(str())] = self.encode_string
        self.encode_func[type(int())] = self.encode_integer
        self.encode_func[type(long())] = self.encode_integer
        self.encode_func[type(list())] = self.encode_list
        self.encode_func[type(dict())] = self.encode_dictionary

        # decoded torrent structure
        self.content = self.decode(content)

    def get_filelist(self):
        """Return array containing fileinfo dictionaries (name, length, path)"""
        files = []
        # single file torrent
        if 'length' in self.content['info']:
            t = {}
            t['name'] = self.content['info']['name'].decode('utf-8')
            t['size'] = self.content['info']['length']
            t['path'] = ''
            files.append(t)
        else:
            # multifile torrent
            for item in self.content['info']['files']:
                t = {}
                t['path'] = '/'.join(item['path'][:-1])
                t['name'] = item['path'][-1].decode('utf-8')
                t['size'] = item['length']
                files.append(t)
        return files

    def get_size(self):
        """Return total size of the torrent"""
        size = 0
        # single file torrent
        if 'length' in self.content['info']:
            size = int(self.content['info']['length'])
        else:
            # multifile torrent
            for item in self.content['info']['files']:
                size += int(item['length'])
        return size

    def get_multitrackers(self):
        """
        Return array containing all multi-trackers in this torrent.
        Returns empty array if torrent has only standard single announce url.
        """
        trackers = []
        # the spec says, if announce-list present use ONLY that
        # funny iteration because of nesting, ie:
        # [ [ tracker1, tracker2 ], [backup1] ]
        for tl in self.content.get('announce-list', []):
            for t in tl:
                trackers.append(t)
        return trackers

    def get_info_hash(self):
        """Return Torrent info hash"""
        import hashlib
        hash = hashlib.sha1()
        info_data = self.encode_dictionary(self.content['info'])
        hash.update(info_data)
        return hash.hexdigest().upper()

    def get_comment(self):
        return self.content['comment']

    def set_comment(self, comment):
        self.content['comment'] = comment

    def remove_multitracker(self, tracker):
        """Removes passed multi-tracker from this torrent"""
        for tl in self.content.get('announce-list', [])[:]:
            try:
                tl.remove(tracker)
                # if no trackers left in list, remove whole list
                if not tl:
                    self.content['announce-list'].remove(tl)
            except:
                pass

    def add_multitracker(self, tracker):
        """Appends multi-tracker to this torrent"""
        self.content.setdefault('announce-list', [])
        self.content['announce-list'].append(tracker)

    def __str__(self):
        return '<Torrent instance. Files: %s>' % self.get_filelist()

    def tokenize(self, text, match=re.compile("([idel])|(\d+):|(-?\d+)").match):
        i = 0
        while i < len(text):
            m = match(text, i)
            s = m.group(m.lastindex)
            i = m.end()
            if m.lastindex == 2:
                yield "s"
                yield text[i:i + int(s)]
                i = i + int(s)
            else:
                yield s

    def decode_item(self, next, token):
        if token == "i":
            # integer: "i" value "e"
            data = int(next())
            if next() != "e":
                raise ValueError
        elif token == "s":
            # string: "s" value (virtual tokens)
            data = next()
        elif token == "l" or token == "d":
            # container: "l" (or "d") values "e"
            data = []
            tok = next()
            while tok != "e":
                data.append(self.decode_item(next, tok))
                tok = next()
            if token == "d":
                data = dict(zip(data[0::2], data[1::2]))
        else:
            raise ValueError
        return data

    def decode(self, text):
        try:
            src = self.tokenize(text)
            data = self.decode_item(src.next, src.next()) # pylint:disable=E1101
            for token in src: # look for more tokens
                raise SyntaxError("trailing junk")
        except (AttributeError, ValueError, StopIteration):
            raise SyntaxError("syntax error")
        return data

    # encoding implementation by d0b

    def encode_string(self, data):
        return "%d:%s" % (len(data), data)

    def encode_integer(self, data):
        return "i%de" % data

    def encode_list(self, data):
        encoded = "l"
        for item in data:
            encoded += self.encode_func[type(item)](item)
        encoded += "e"
        return encoded

    def encode_dictionary(self, data):
        encoded = "d"
        items = data.items()
        items.sort()
        for (key, value) in items:
            encoded += self.encode_string(key)
            encoded += self.encode_func[type(value)](value)
        encoded += "e"
        return encoded

    def encode(self):
        data = self.content
        return self.encode_func[type(data)](data)


class TorrentFilename(object):

    """
        Makes sure that entries containing torrent-file have .torrent
        extension. This is enabled always by default (builtins).
    """

    @priority(255)
    def on_feed_modify(self, feed):
        for entry in feed.accepted + [i for i in feed.entries if i not in feed.entries]:
            # skip if entry does not have file assigned
            if not 'file' in entry:
                log.log(5, '%s doesn\'t have a file associated' % entry['title'])
                continue
            f = open(entry['file'], 'rb')
            data = f.read(200)
            f.close()
            if not TORRENT_RE.match(data):
                # not a torrent file at all, skip
                log.log(5, '%s doesn\'t seem to be a torrent' % entry['title'])
                continue
            else:
                log.debug('%s seems to be a torrent' % entry['title'])

            # create torrent object from torrent
            try:
                f = open(entry['file'], 'rb')
                # NOTE: this reads entire file into memory, but we're pretty sure it's
                # a small torrent file since it starts with idstr
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
                if 'filename' in entry:
                    if not entry['filename'].lower().endswith('.torrent'):
                        # filename present but without .torrent extension, add it
                        entry['filename'] = '%s.torrent' % entry['filename']
                else:
                    # generate filename from torrent or fall back to title plus extension
                    entry['filename'] = self.make_filename(torrent, entry)
            except Exception, e:
                log.exception(e)

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

        #title = title.encode('iso8859-1', 'ignore') # Damn \u200b -character, how I loathe thee
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
