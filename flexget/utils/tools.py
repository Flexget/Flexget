"""Contains miscellaneous helpers"""

import urllib2
import httplib
import socket
from urlparse import urlparse
import time
from htmlentitydefs import name2codepoint
import re
import ntpath
from datetime import timedelta, datetime


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


class MergeException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def strip_html(text):
    """Tries to strip all HTML tags from :text:. If unsuccessful returns original text."""
    from BeautifulSoup import BeautifulSoup
    try:
        text = ' '.join(BeautifulSoup(text).findAll(text=True))
        return ' '.join(text.split())
    except:
        return text


# This pattern matches a character entity reference (a decimal numeric
# references, a hexadecimal numeric reference, or a named reference).
charrefpat = re.compile(r'&(#(\d+|x[\da-fA-F]+)|[\w.:-]+);?')


def _htmldecode(text):
    """Decode HTML entities in the given text."""
    # From screpe.py - licensed under apache 2.0 .. should not be a problem for a MIT afaik
    if type(text) is unicode:
        uchr = unichr
    else:
        uchr = lambda value: value > 127 and unichr(value) or chr(value)

    def entitydecode(match, uchr=uchr):
        entity = match.group(1)
        if entity.startswith('#x'):
            return uchr(int(entity[2:], 16))
        elif entity.startswith('#'):
            return uchr(int(entity[1:]))
        elif entity in name2codepoint:
            return uchr(name2codepoint[entity])
        else:
            return match.group(0)
    return charrefpat.sub(entitydecode, text)


def decode_html(value):
    """Decode HTML entities from :value: and return it"""

    """
    fails to decode &#x2500;

    from BeautifulSoup import BeautifulSoup
    return unicode(BeautifulSoup(value, convertEntities=BeautifulSoup.HTML_ENTITIES))
    """

    return _htmldecode(value)


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
    # Phase through the unicode_data string one character at a time in
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
            elif isinstance(v, basestring) and isinstance(d2[k], basestring):
                # Strings are compatible by definition
                # (though we could get a decode error later, this is higly unlikely for config values)
                pass
            else:
                raise MergeException('Merging key %s failed, conflicting datatypes %r vs. %r.' % (
                    k, type(v).__name__, type(d2[k]).__name__))
        else:
            d2[k] = copy.deepcopy(v)


class SmartRedirectHandler(urllib2.HTTPRedirectHandler):

    def http_error_301(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_301(self, req, fp, code, msg, headers)
        result.status = code
        return result

    def http_error_302(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        result.status = code
        return result

# Remembers sites that have timed out
unresponsive_sites = {}
# Time to wait before trying an unresponsive site again
WAIT_TIME = timedelta(seconds=60)


def urlopener(url, log, **kwargs):
    """Utility function for pulling back a url, with a retry of 3 times, increasing the timeout, etc.
    Should be grabbing all urls this way eventually, to keep error handling code in the same place."""

    # get the old timeout for sockets, so we can set it back to that when done. This is NOT threadsafe by the way.
    # In order to avoid requiring python 2.6, we're not using the urlopen timeout parameter. That really should be used
    # after checking for python 2.6.

    if isinstance(url, urllib2.Request):
        site = url.get_host()
    else:
        site = urlparse(url).netloc
    if site in unresponsive_sites:
        if unresponsive_sites[site] > datetime.now() - WAIT_TIME:
            msg = ('%s is unresponsive, not trying again for %s seconds.' %
                  (site, (WAIT_TIME - (datetime.now() - unresponsive_sites[site])).seconds))
            log.warning(msg)
            raise urllib2.URLError(msg)

    retries = kwargs.get('retries', 3)
    oldtimeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(15.0)

        handlers = [SmartRedirectHandler()]
        if urllib2._opener:
            handlers.extend(urllib2._opener.handlers)
        if kwargs.get('handlers'):
            handlers.extend(kwargs['handlers'])
        if len(handlers) > 1:
            handler_names = [h.__class__.__name__ for h in handlers]
            log.debug('Additional handlers have been specified for this urlopen: %s' % ', '.join(handler_names))
        opener = urllib2.build_opener(*handlers).open
        for i in range(retries): # retry getting the url up to 3 times.
            if i > 0:
                time.sleep(3)
            try:
                retrieved = opener(url, kwargs.get('data'))
            except urllib2.HTTPError, e:
                if e.code < 500:
                    # If it was not a server error, don't keep retrying.
                    log.warning('Could not retrieve url (HTTP %s error): %s' % (e.code, e.url))
                    raise
                log.debug('HTTP error (try %i/%i): %s' % (i + 1, retries, e.code))
            except (urllib2.URLError, socket.timeout), e:
                if hasattr(e, 'reason'):
                    reason = str(e.reason)
                else:
                    reason = 'N/A'
                if reason == 'timed out':
                    unresponsive_sites[site] = datetime.now()
                log.debug('Failed to retrieve url (try %i/%i): %s' % (i + 1, retries, reason))
            except httplib.IncompleteRead, e:
                log.critical('Incomplete read - see python bug 6312')
                break
            else:
                # We were successful, removie this site from unresponsive_sites
                unresponsive_sites.pop(site, None)

                # make the returned instance usable in a with statement by adding __enter__ and __exit__ methods

                def enter(self):
                    return self

                def exit(self, exc_type, exc_val, exc_tb):
                    self.close()

                retrieved.__class__.__enter__ = enter
                retrieved.__class__.__exit__ = exit
                return retrieved

        log.warning('Could not retrieve url: %s' % url)
        raise urllib2.URLError('Could not retrieve url after %s tries.' % retries)
    finally:
        socket.setdefaulttimeout(oldtimeout)


class ReList(list):
    """
    A list that stores regexps.

    You can add compiled or uncompiled regexps to the list.
    It will always return the compiled version.
    It will compile the text regexps on demand when first accessed.
    """

    # Set the default flags
    flags = re.IGNORECASE | re.UNICODE

    def __init__(self, *args, **kwargs):
        """Optional :flags: keyword argument with regexp flags to compile with"""
        if 'flags' in kwargs:
            self.flags = kwargs['flags']
            del kwargs['flags']
        list.__init__(self, *args, **kwargs)

    def __getitem__(self, k):
        item = list.__getitem__(self, k)
        if isinstance(item, basestring):
            item = re.compile(item, re.IGNORECASE | re.UNICODE)
            self[k] = item
        return item

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]


def make_valid_path(path, windows=None):
    """Removes invalid characters from windows pathnames"""
    drive, path = ntpath.splitdrive(path)
    if windows is None and drive:
        # If a drive is found, this is a windows path
        windows = True
    if windows:
        # Remove invalid characters
        for char in ':<>*?"|':
            path = path.replace(char, '')
        # Windows directories and files cannot end with period
        path = re.sub(r'(?<![\./\\])\.+(?=[/\\]|$)', '', path)
    return drive + path


def console(text):
    """Safe print to console."""

    if isinstance(text, str):
        print text
        return

    print unicode(text).encode('utf8')


def parse_timedelta(value):
    if isinstance(value, timedelta):
        # Allow timedelta objects to pass through
        return value
    if not value:
        # If no time is given, default to 0
        return timedelta()
    amount, unit = value.lower().split(' ')
    # Make sure unit name is plural.
    if not unit.endswith('s'):
        unit += 's'
    params = {unit: int(amount)}
    try:
        return timedelta(**params)
    except TypeError:
        raise ValueError('Invalid time format \'%s\'' % value)
