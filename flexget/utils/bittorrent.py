"""Torrenting utils, mostly for handling bencoding and torrent files."""
# Torrent decoding is a short fragment from effbot.org. Site copyright says:
# Test scripts and other short code fragments can be considered as being in the public domain.
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import binascii
import functools
import re
import logging

log = logging.getLogger('torrent')

# Magic indicator used to quickly recognize torrent files
TORRENT_RE = re.compile(br'^d\d{1,3}:')

# List of all standard keys in a metafile
# See http://packages.python.org/pyrocore/apidocs/pyrocore.util.metafile-module.html#METAFILE_STD_KEYS
METAFILE_STD_KEYS = [i.split('.') for i in (
    "announce",
    "announce-list",  # BEP-0012
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

    for key in list(meta.keys()):
        if [key] not in METAFILE_STD_KEYS:
            if logger:
                logger("Removing key %r..." % (key,))
            del meta[key]
            modified.add(key)

    if including_info:
        for key in list(meta["info"].keys()):
            if ["info", key] not in METAFILE_STD_KEYS:
                if logger:
                    logger("Removing key %r..." % ("info." + key,))
                del meta["info"][key]
                modified.add("info." + key)

        for idx, entry in enumerate(meta["info"].get("files", [])):
            for key in list(entry.keys()):
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
    with open(metafilepath, 'rb') as f:
        data = f.read(200)

    magic_marker = bool(TORRENT_RE.match(data))
    if not magic_marker:
        log.trace('%s doesn\'t seem to be a torrent, got `%s` (hex)' % (metafilepath, binascii.hexlify(data)))

    return bool(magic_marker)


def tokenize(text, match=re.compile(b'([idel])|(\d+):|(-?\d+)').match):
    i = 0
    while i < len(text):
        m = match(text, i)
        s = m.group(m.lastindex)
        i = m.end()
        if m.lastindex == 2:
            yield b's'
            yield text[i:i + int(s)]
            i += int(s)
        else:
            yield s


def decode_item(next, token):
    if token == b'i':
        # integer: "i" value "e"
        data = int(next())
        if next() != b'e':
            raise ValueError
    elif token == b's':
        # string: "s" value (virtual tokens)
        data = next()
        # Strings in torrent file are defined as utf-8 encoded
        try:
            data = data.decode('utf-8')
        except UnicodeDecodeError:
            # The pieces field is a byte string, and should be left as such.
            pass
    elif token == b'l' or token == b'd':
        # container: "l" (or "d") values "e"
        data = []
        tok = next()
        while tok != b'e':
            data.append(decode_item(next, tok))
            tok = next()
        if token == b'd':
            data = dict(list(zip(data[0::2], data[1::2])))
    else:
        raise ValueError
    return data


def bdecode(text):
    try:
        src = tokenize(text)
        data = decode_item(functools.partial(next, src), next(src))  # pylint:disable=E1101
        for _ in src:  # look for more tokens
            raise SyntaxError("trailing junk")
    except (AttributeError, ValueError, StopIteration, TypeError) as e:
        raise SyntaxError("syntax error: %s" % e)
    return data


# encoding implementation by d0b
def encode_string(data):
    return encode_bytes(data.encode('utf-8'))


def encode_bytes(data):
    return str(len(data)).encode() + b':' + data


def encode_integer(data):
    return b'i' + str(data).encode() + b'e'


def encode_list(data):
    encoded = b'l'
    for item in data:
        encoded += bencode(item)
    encoded += b'e'
    return encoded


def encode_dictionary(data):
    encoded = b'd'
    items = list(data.items())
    items.sort()
    for (key, value) in items:
        encoded += bencode(key)
        encoded += bencode(value)
    encoded += b'e'
    return encoded


def bencode(data):
    if isinstance(data, bytes):
        return encode_bytes(data)
    if isinstance(data, str):
        return encode_string(data)
    if isinstance(data, int):
        return encode_integer(data)
    if isinstance(data, list):
        return encode_list(data)
    if isinstance(data, dict):
        return encode_dictionary(data)

    raise TypeError


class Torrent(object):
    """Represents a torrent"""
    # string type used for keys, if this ever changes, stuff like "x in y"
    # gets broken unless you coerce to this type
    KEY_TYPE = str

    @classmethod
    def from_file(cls, filename):
        """Create torrent from file on disk."""
        with open(filename, 'rb') as handle:
            return cls(handle.read())

    def __init__(self, content):
        """Accepts torrent file as string"""
        # Make sure there is no trailing whitespace. see #1592
        content = content.strip()
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
            t = {'name': self.content['info']['name'],
                 'size': self.content['info']['length'],
                 'path': ''}
            files.append(t)
        else:
            # multifile torrent
            for item in self.content['info']['files']:
                t = {'path': '/'.join(item['path'][:-1]),
                     'name': item['path'][-1],
                     'size': item['length']}
                files.append(t)

        # Decode strings
        for item in files:
            for field in ('name', 'path'):
                # These should already be decoded if they were utf-8, if not we can try some other stuff
                if not isinstance(item[field], str):
                    try:
                        item[field] = item[field].decode(self.content.get('encoding', 'cp1252'))
                    except UnicodeError:
                        # Broken beyond anything reasonable
                        fallback = item[field].decode('utf-8', 'replace').replace(u'\ufffd', '_')
                        log.warning('%s=%r field in torrent %r is wrongly encoded, falling back to `%s`' %
                                    (field, item[field], self.content['info']['name'], fallback))
                        item[field] = fallback

        return files

    @property
    def size(self):
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

    @property
    def trackers(self):
        """
        :returns: List of trackers, supports single-tracker and multi-tracker implementations
        """
        trackers = []
        # the spec says, if announce-list present use ONLY that
        # funny iteration because of nesting, ie:
        # [ [ tracker1, tracker2 ], [backup1] ]
        for tl in self.content.get('announce-list', []):
            for t in tl:
                trackers.append(t)
        if not self.content.get('announce') in trackers:
            trackers.append(self.content.get('announce'))
        return trackers

    @property
    def info_hash(self):
        """Return Torrent info hash"""
        import hashlib
        hash = hashlib.sha1()
        info_data = encode_dictionary(self.content['info'])
        hash.update(info_data)
        return str(hash.hexdigest().upper())

    @property
    def comment(self):
        return self.content['comment']

    @comment.setter
    def comment(self, comment):
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
            except (AttributeError, ValueError):
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
