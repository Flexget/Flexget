"""Contains miscellaneous helpers"""

import sgmllib

class HtmlParser(sgmllib.SGMLParser):
    from htmlentitydefs import entitydefs

    def __init__(self, s=None):
        sgmllib.SGMLParser.__init__(self)
        self.result = ''
        if s:
            self.feed(s)

    def handle_entityref(self, name):
        if self.entitydefs.has_key(name):
            x = ';'
        else:
            x = ''
        self.result = '%s&%s%s' % (self.result, name, x)

    def handle_data(self, data):
        if data:
            self.result += data

class MergeException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

def decode_html(value):
    """Decode HTML entities from string and return it"""
    parser = HtmlParser(value)
    return parser.result


def encode_html(unicode_data, encoding='ascii'):
    """
    Encode unicode_data for use as XML or HTML, with characters outside
    of the encoding converted to XML numeric character references.
    """
    try:
        return unicode_data.encode(encoding, 'xmlcharrefreplace')
    except ValueError:
        # ValueError is raised if there are unencodable chars in the
        # data and the 'xmlcharrefreplace' error handler is not found.
        # Pre-2.3 Python doesn't support the 'xmlcharrefreplace' error
        # handler, so we'll emulate it.
        return _xmlcharref_encode(unicode_data, encoding)

def _xmlcharref_encode(unicode_data, encoding):
    """Emulate Python 2.3's 'xmlcharrefreplace' encoding error handler."""
    chars = []
    # Step through the unicode_data string one character at a time in
    # order to catch unencodable characters:
    for char in unicode_data:
        try:
            chars.append(char.encode(encoding, 'strict'))
        except UnicodeError:
            chars.append('&#%i;' % ord(char))
    return ''.join(chars)

def sanitize(d, logger=None):
    """Makes dictionary d contain only yaml.safe_dump compatible elements. On other words, remove all non
    standard types from dictionary."""
    import types
    valid = [types.DictType, types.IntType, types.NoneType,
             types.StringType, types.UnicodeType, types.BooleanType,
             types.ListType, types.LongType, types.FloatType]
    for k in d.keys():
        if type(d[k])==types.ListType:
            for i in d[k][:]:
                if not type(i) in valid:
                    if logger:
                        logger.debug('Removed non yaml compatible list item from key %s %s' % (k, type([k])))
                    d[k].remove(i)
        if type(d[k])==types.DictType:
            sanitize(d[k])
        if not type(d[k]) in valid:
            if logger:
                logger.debug('Removed non yaml compatible key %s %s' % (k, type(d[k])))
            d.pop(k)


def merge_dict_from_to(d1, d2):
    """Merges dictionary d1 into dictionary d2. d1 will remain in original form."""
    for k, v in d1.items():
        if k in d2:
            if type(v) == type(d2[k]):
                if isinstance(v, dict):
                    merge_dict_from_to(d1[k], d2[k])
                elif isinstance(v, list):
                    d2[k].extend(v)
                elif isinstance(v, basestring) or isinstance(v, bool) or isinstance(v, int):
                    pass
                else:
                    raise Exception('Unknown type: %s value: %s in dictionary' % (type(v), repr(v)))
            else:
                raise MergeException('Merging key %s failed, conflicting datatypes.' % (k))
        else:
            d2[k] = v


