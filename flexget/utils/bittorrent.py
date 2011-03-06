"""Torrenting utils, mostly for handling bencoding and torrent files."""
# Torrent decoding is a short fragment from effbot.org. Site copyright says:
# Test scripts and other short code fragments can be considered as being in the public domain.
import re
import logging

log = logging.getLogger('torrent')

# Magic indicator used to quickly recognize torrent files
TORRENT_RE = re.compile(r'^d\d{1,3}:')

# List of all standard keys in a metafile
# See http://packages.python.org/pyrocore/apidocs/pyrocore.util.metafile-module.html#METAFILE_STD_KEYS
METAFILE_STD_KEYS = [i.split('.') for i in (
    "announce",
    "comment",
    "created by",
    "creation date",
    "encoding",
    "info",
    "info.length",
    "info.name",
    "info.piece length",
    "info.pieces",
    "info.private",
    "info.files",
    "info.files.length",
    "info.files.path",
)]


def clean_meta(meta, including_info=False, logger=None):
    """ Clean meta dict. Optionally log changes to the given logger at INFO level.
    
        See also http://packages.python.org/pyrocore/apidocs/pyrocore.util.metafile-pysrc.html#clean_meta
        
        @return: True if C{meta} was modified.
    """
    modified = False

    for key in meta.keys():
        if [key] not in METAFILE_STD_KEYS:
            if logger:
                logger.info("Removing key %r..." % (key,))
            del meta[key]
            modified = True

    if including_info:
        for key in meta["info"].keys():
            if ["info", key] not in METAFILE_STD_KEYS:
                if logger: 
                    logger.info("Removing key %r..." % ("info." + key,))
                del meta["info"][key]
                modified = True

        for idx, entry in enumerate(meta["info"].get("files", [])):
            for key in entry.keys():
                if ["info", "files", key] not in METAFILE_STD_KEYS:
                    if logger: 
                        logger.info("Removing key %r from file #%d..." % (key, idx + 1))
                    del entry[key]
                    modified = True

    return modified


def is_torrent_file(metafilepath):
    """ Check whether a file looks like a metafile by peeking into its content.
    
        Note that this doesn't ensure that the file is a complete and valid torrent,
        it just allows fast filtering of candidate files.
        
        @param metafilepath: Path to the file to check, must have read permissions for it.
        @return: True if there is a high probability this is a metafile. 
    """
    f = open(metafilepath, 'rb')
    try:
        # read first 200 bytes to verify if a file is a torrent or not
        data = f.read(200)
    finally:
        f.close()

    magic_marker = bool(TORRENT_RE.match(data))
    if not magic_marker:
        log.debugall('%s doesn\'t seem to be a torrent, got `%s` (hex)' % (metafilepath, data.encode('hex')))

    return bool(magic_marker)


class Torrent(object):
    """Represents a torrent"""

    @classmethod
    def from_file(cls, filename):
        """Create torrent from file on disk."""
        handle = open(filename, 'rb')
        try:
            return cls(handle.read())
        finally:
            handle.close()

    def __init__(self, content):
        """Accepts torrent file as string"""

        # decoded torrent structure
        self.content = self.decode(content)
        self.modified = False

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

    @property
    def private(self):
        return self.content['info'].get('private', False)

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
        self.modified = True

    def remove_multitracker(self, tracker):
        """Removes passed multi-tracker from this torrent"""
        for tl in self.content.get('announce-list', [])[:]:
            try:
                tl.remove(tracker)
                self.modified = True
                # if no trackers left in list, remove whole list
                if not tl:
                    self.content['announce-list'].remove(tl)
            except:
                pass

    def add_multitracker(self, tracker):
        """Appends multi-tracker to this torrent"""
        self.content.setdefault('announce-list', [])
        self.content['announce-list'].append([tracker])
        self.modified = True

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

    def encode_unicode(self, data):
        return self.encode_string(str(data))

    def encode_integer(self, data):
        return "i%de" % data

    def encode_list(self, data):
        encoded = "l"
        for item in data:
            encoded += self.encode_func(item)
        encoded += "e"
        return encoded

    def encode_dictionary(self, data):
        encoded = "d"
        items = data.items()
        items.sort()
        for (key, value) in items:
            encoded += self.encode_string(key)
            encoded += self.encode_func(value)
        encoded += "e"
        return encoded

    def encode_func(self, data):
        encode_func = {
            str: self.encode_string,
            unicode: self.encode_unicode,
            int: self.encode_integer,
            long: self.encode_integer,
            list: self.encode_list,
            dict: self.encode_dictionary}
        return encode_func[type(data)](data)

    def encode(self):
        data = self.content
        return self.encode_func(data)
