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
    "announce-list", # BEP-0012
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
    """ Clean meta dict. Optionally log changes using the given logger.

        See also http://packages.python.org/pyrocore/apidocs/pyrocore.util.metafile-pysrc.html#clean_meta

        @param logger: If given, a callable accepting a string message.
        @return: Set of keys removed from C{meta}.
    """
    modified = set()

    for key in meta.keys():
        if [key] not in METAFILE_STD_KEYS:
            if logger:
                logger("Removing key %r..." % (key,))
            del meta[key]
            modified.add(key)

    if including_info:
        for key in meta["info"].keys():
            if ["info", key] not in METAFILE_STD_KEYS:
                if logger:
                    logger("Removing key %r..." % ("info." + key,))
                del meta["info"][key]
                modified.add("info." + key)

        for idx, entry in enumerate(meta["info"].get("files", [])):
            for key in entry.keys():
                if ["info", "files", key] not in METAFILE_STD_KEYS:
                    if logger:
                        logger("Removing key %r from file #%d..." % (key, idx + 1))
                    del entry[key]
                    modified.add("info.files." + key)

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
        log.trace('%s doesn\'t seem to be a torrent, got `%s` (hex)' % (metafilepath, data.encode('hex')))

    return bool(magic_marker)


def tokenize(text, match=re.compile("([idel])|(\d+):|(-?\d+)").match):
    i = 0
    # Make sure there is no trailing whitespace. see #1592
    text = text.strip()
    while i < len(text):
        m = match(text, i)
        s = m.group(m.lastindex)
        i = m.end()
        if m.lastindex == 2:
            yield "s"
            yield text[i:i + int(s)]
            i += int(s)
        else:
            yield s


def decode_item(next, token):
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
            data.append(decode_item(next, tok))
            tok = next()
        if token == "d":
            data = dict(zip(data[0::2], data[1::2]))
    else:
        raise ValueError
    return data


def bdecode(text):
    try:
        src = tokenize(text)
        data = decode_item(src.next, src.next()) # pylint:disable=E1101
        for token in src: # look for more tokens
            raise SyntaxError("trailing junk")
    except (AttributeError, ValueError, StopIteration):
        raise SyntaxError("syntax error")
    return data


# encoding implementation by d0b
def encode_string(data):
    return "%d:%s" % (len(data), data)


def encode_unicode(data):
    return encode_string(str(data))


def encode_integer(data):
    return "i%de" % data


def encode_list(data):
    encoded = "l"
    for item in data:
        encoded += bencode(item)
    encoded += "e"
    return encoded


def encode_dictionary(data):
    encoded = "d"
    items = data.items()
    items.sort()
    for (key, value) in items:
        encoded += encode_string(key)
        encoded += bencode(value)
    encoded += "e"
    return encoded


def bencode(data):
    encode_func = {
        str: encode_string,
        unicode: encode_unicode,
        int: encode_integer,
        long: encode_integer,
        list: encode_list,
        dict: encode_dictionary}
    return encode_func[type(data)](data)


class Torrent(object):
    """Represents a torrent"""
    # string type used for keys, if this ever changes, stuff like "x in y"
    # gets broken unless you coerce to this type
    KEY_TYPE = str

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
        self.content = bdecode(content)
        self.modified = False

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__,
            ", ".join("%s=%r" % (key, self.content["info"].get(key))
               for key in ("name", "length", "private",)),
            ", ".join("%s=%r" % (key, self.content.get(key))
               for key in ("announce", "comment",)))

    def get_filelist(self):
        """Return array containing fileinfo dictionaries (name, length, path)"""
        files = []
        if 'length' in self.content['info']:
            # single file torrent
            t = {}
            t['name'] = self.content['info']['name']
            t['size'] = self.content['info']['length']
            t['path'] = ''
            files.append(t)
        else:
            # multifile torrent
            for item in self.content['info']['files']:
                t = {}
                t['path'] = '/'.join(item['path'][:-1])
                t['name'] = item['path'][-1]
                t['size'] = item['length']
                files.append(t)

        # Decode strings
        for item in files:
            for field in ('name', 'path'):
                # The standard mandates UTF-8, but try other common things
                for encoding in ('utf-8', self.content.get('encoding', None), 'cp1252'):
                    if encoding:
                        try:
                            item[field] = item[field].decode(encoding)
                            break
                        except UnicodeError:
                            continue
                else:
                    # Broken beyond anything reasonable
                    fallback = unicode(item[field], 'utf-8', 'replace').replace(u'\ufffd', '_')
                    log.warning("%s=%r field in torrent %r is wrongly encoded, falling back to '%s'" % (
                        field, item[field], self.content['info']['name'], fallback))
                    item[field] = fallback

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
        info_data = encode_dictionary(self.content['info'])
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

    def encode(self):
        return bencode(self.content)
