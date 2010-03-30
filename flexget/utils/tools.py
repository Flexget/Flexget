"""Contains miscellaneous helpers"""

import sgmllib
import urllib2
import socket
import time
import gzip
import StringIO


def str_to_boolean(string):
    if string.lower() in ['true', '1', 't', 'y', 'yes']:
        return True
    else:
        return False


def convert_bytes(bytes):
    """Returns given bytes as prettified string."""

    bytes = float(bytes)
    if bytes >= 1099511627776:
        terabytes = bytes / 1099511627776
        size = '%.2fT' % terabytes
    elif bytes >= 1073741824:
        gigabytes = bytes / 1073741824
        size = '%.2fG' % gigabytes
    elif bytes >= 1048576:
        megabytes = bytes / 1048576
        size = '%.2fM' % megabytes
    elif bytes >= 1024:
        kilobytes = bytes / 1024
        size = '%.2fK' % kilobytes
    else:
        size = '%.2fb' % bytes
    return size


class HtmlParser(sgmllib.SGMLParser):
    from htmlentitydefs import entitydefs

    def __init__(self, s=None):
        sgmllib.SGMLParser.__init__(self)
        self.result = ''
        if s:
            self.feed(s)

    def handle_entityref(self, name):
        if name in self.entitydefs:
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


import types
_valid = [types.DictType, types.IntType, types.NoneType,
          types.StringType, types.UnicodeType, types.BooleanType,
          types.ListType, types.LongType, types.FloatType]


# TODO: I think this was left as broken ...
def sanitize(value, logger=None):
    raise Exception('broken')
    if isinstance(value, dict):
        sanitize_dict(value, logger)
    elif isinstance(value, list):
        sanitize_list(value, logger)
    else:
        raise Exception('Unsupported datatype')


# TODO: I think this was left as broken ...
def sanitize_dict(d, logger=None):
    """Makes dictionary d contain only yaml.safe_dump compatible elements. On other words, remove all non
    standard types from dictionary."""
    for k in d.keys():
        if isinstance(type(d[k]), list):
            sanitize_list(d[k])
        elif isinstance(type(d[k]), dict):
            sanitize_dict(d[k], logger)
        elif not type(d[k]) in _valid:
            if logger:
                logger.debug('Removed non yaml compatible key %s %s' % (k, type(d[k])))
            d.pop(k)


# TODO: I think this was left as broken ...
def sanitize_list(content, logger=None):
    for value in content[:]:
        if not type(value) in _valid:
            if logger:
                logger.debug('Removed non yaml compatible list item %s' % type(value))
        content.remove(value)


def merge_dict_from_to(d1, d2):
    """Merges dictionary d1 into dictionary d2. d1 will remain in original form."""
    import copy
    for k, v in d1.items():
        if k in d2:
            if type(v) == type(d2[k]):
                if isinstance(v, dict):
                    merge_dict_from_to(d1[k], d2[k])
                elif isinstance(v, list):
                    d2[k].extend(copy.deepcopy(v))
                elif isinstance(v, basestring) or isinstance(v, bool) or \
                     isinstance(v, int) or isinstance(v, float):
                    pass
                else:
                    raise Exception('Unknown type: %s value: %s in dictionary' % (type(v), repr(v)))
            else:
                raise MergeException('Merging key %s failed, conflicting datatypes.' % (k))
        else:
            d2[k] = copy.deepcopy(v)


def urlopener(url, log, **kwargs):
    """Utility function for pulling back a url, with a retry of 3 times, increasing the timeout, etc. 
    Should be grabbing all urls this way eventually, to keep error handling code in the same place."""
    # get the old timeout for sockets, so we can set it back to that when done. This is NOT threadsafe by the way.
    # In order to avoid requiring python 2.6, we're not using the urlopen timeout parameter. That really should be used
    # after checking for python 2.6.
    oldtimeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(15.0)
    # Apparently isinstance is considered unpythonic. So doing this instead.
    #try:
    #    url.add_header("Accept-encoding", "gzip, deflate")
    #except AttributeError:
    #    url = urllib2.Request(url)
    #    url.add_header("Accept-encoding", "gzip, deflate")
    for i in range(3): # retry getting the url up to 3 times.
        sleep = True
        try:
            retrieved = urllib2.urlopen(url)
            sleep = False
        except urllib2.URLError, e:
            log.debug('Failed to retrieve url (try %i/3): %s' % (i + 1, str(e.reason)))
        except urllib2.HTTPError, e:
            log.debug('HTTP error (try %i/3): %s' % (i + 1, str(e.code)))
        else:
            socket.setdefaulttimeout(oldtimeout)
            #data = retrieved.read()
            #if retrieved.headers.get('content-encoding', None) == 'gzip':
            #    log.debug("found gzipped response")
            #    data = gzip.GzipFile(fileobj=StringIO.StringIO(data)).read()
            return retrieved
        finally:
            if sleep:
                time.sleep(3)
    log.warning('Could not retrieve url: %s' % url)
    socket.setdefaulttimeout(oldtimeout)
    raise urllib2.URLError("Could not retrieve url after 3 retries.")
