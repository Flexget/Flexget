"""Contains miscellaneous helpers"""

from __future__ import unicode_literals, division, absolute_import, print_function
import copy
import urllib2
import httplib
import os
import socket
import time
import re
import sys
import locale
import Queue
import ast
import operator

from collections import MutableMapping
from urlparse import urlparse
from htmlentitydefs import name2codepoint
from datetime import timedelta, datetime


def str_to_boolean(string):
    if string.lower() in ['true', '1', 't', 'y', 'yes']:
        return True
    else:
        return False


def str_to_int(string):
    try:
        return int(string.replace(',', ''))
    except ValueError:
        return None


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
    """Tries to strip all HTML tags from *text*. If unsuccessful returns original text."""
    from bs4 import BeautifulSoup
    try:
        text = ' '.join(BeautifulSoup(text).find_all(text=True))
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
    """
    :param string value: String to be html-decoded
    :returns: Html decoded string
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


def merge_dict_from_to(d1, d2):
    """Merges dictionary d1 into dictionary d2. d1 will remain in original form."""
    for k, v in d1.items():
        if k in d2:
            if type(v) == type(d2[k]):
                if isinstance(v, dict):
                    merge_dict_from_to(d1[k], d2[k])
                elif isinstance(v, list):
                    d2[k].extend(copy.deepcopy(v))
                elif isinstance(v, (basestring, bool, int, float, type(None))):
                    pass
                else:
                    raise Exception('Unknown type: %s value: %s in dictionary' % (type(v), repr(v)))
            elif (isinstance(v, (basestring, bool, int, float, type(None))) and
                    isinstance(d2[k], (basestring, bool, int, float, type(None)))):
                # Allow overriding of non-container types with other non-container types
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


def urlopener(url_or_request, log, **kwargs):
    """
    Utility function for pulling back a url, with a retry of 3 times, increasing the timeout, etc.
    Re-raises any errors as URLError.

    .. warning:: This is being replaced by requests library.
                 flexget.utils.requests should be used going forward.

    :param str url_or_request: URL or Request object to get.
    :param log: Logger to log debug info and errors to
    :param kwargs: Keyword arguments to be passed to urlopen
    :return: The file-like object returned by urlopen
    """
    from flexget.utils.requests import is_unresponsive, set_unresponsive

    if isinstance(url_or_request, urllib2.Request):
        url = url_or_request.get_host()
    else:
        url = url_or_request
    if is_unresponsive(url):
        msg = '%s is known to be unresponsive, not trying again.' % urlparse(url).hostname
        log.warning(msg)
        raise urllib2.URLError(msg)

    retries = kwargs.get('retries', 3)
    timeout = kwargs.get('timeout', 15.0)

    # get the old timeout for sockets, so we can set it back to that when done. This is NOT threadsafe by the way.
    # In order to avoid requiring python 2.6, we're not using the urlopen timeout parameter. That really should be used
    # after checking for python 2.6.
    oldtimeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)

        handlers = [SmartRedirectHandler()]
        if urllib2._opener:
            handlers.extend(urllib2._opener.handlers)
        if kwargs.get('handlers'):
            handlers.extend(kwargs['handlers'])
        if len(handlers) > 1:
            handler_names = [h.__class__.__name__ for h in handlers]
            log.debug('Additional handlers have been specified for this urlopen: %s' % ', '.join(handler_names))
        opener = urllib2.build_opener(*handlers).open
        for i in range(retries):  # retry getting the url up to 3 times.
            if i > 0:
                time.sleep(3)
            try:
                retrieved = opener(url_or_request, kwargs.get('data'))
            except urllib2.HTTPError as e:
                if e.code < 500:
                    # If it was not a server error, don't keep retrying.
                    log.warning('Could not retrieve url (HTTP %s error): %s' % (e.code, e.url))
                    raise
                log.debug('HTTP error (try %i/%i): %s' % (i + 1, retries, e.code))
            except (urllib2.URLError, socket.timeout) as e:
                if hasattr(e, 'reason'):
                    reason = str(e.reason)
                else:
                    reason = 'N/A'
                if reason == 'timed out':
                    set_unresponsive(url)
                log.debug('Failed to retrieve url (try %i/%i): %s' % (i + 1, retries, reason))
            except httplib.IncompleteRead as e:
                log.critical('Incomplete read - see python bug 6312')
                break
            else:
                # make the returned instance usable in a with statement by adding __enter__ and __exit__ methods

                def enter(self):
                    return self

                def exit(self, exc_type, exc_val, exc_tb):
                    self.close()

                retrieved.__class__.__enter__ = enter
                retrieved.__class__.__exit__ = exit
                return retrieved

        log.warning('Could not retrieve url: %s' % url_or_request)
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


# Determine the encoding for io
io_encoding = None
if hasattr(sys.stdout, 'encoding'):
    io_encoding = sys.stdout.encoding
if not io_encoding:
    try:
        io_encoding = locale.getpreferredencoding()
    except Exception:
        pass
if not io_encoding:
    # Default to utf8 if nothing can be determined
    io_encoding = 'utf8'
else:
    # Normalize the encoding
    io_encoding = io_encoding.lower()
    if io_encoding == 'cp65001':
        io_encoding = 'utf8'
    elif io_encoding in ['us-ascii', '646', 'ansi_x3.4-1968']:
        io_encoding = 'ascii'


def console(text):
    """Print to console safely."""
    if isinstance(text, str):
        print(text)
        return
    print(unicode(text).encode(io_encoding, 'replace'))


def parse_timedelta(value):
    """Parse a string like '5 days' into a timedelta object. Also allows timedeltas to pass through."""
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
    params = {unit: float(amount)}
    try:
        return timedelta(**params)
    except TypeError:
        raise ValueError('Invalid time format \'%s\'' % value)


def multiply_timedelta(interval, number):
    """timedeltas can not normally be multiplied by floating points. This does that."""
    # Python 2.6 doesn't have total seconds
    total_seconds = interval.seconds + interval.days * 24 * 3600
    return timedelta(seconds=total_seconds * number)

if os.name == 'posix':
    def pid_exists(pid):
        """Check whether pid exists in the current process table."""
        import errno
        if pid < 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError as e:
            return e.errno == errno.EPERM
        else:
            return True
else:
    def pid_exists(pid):
        import ctypes
        import ctypes.wintypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        STILL_ACTIVE = 259

        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
        if handle == 0:
            return False

        # If the process exited recently, a pid may still exist for the handle.
        # So, check if we can get the exit code.
        exit_code = ctypes.wintypes.DWORD()
        is_running = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0
        kernel32.CloseHandle(handle)

        # See if we couldn't get the exit code or the exit code indicates that the
        # process is still running.
        return is_running or exit_code.value == STILL_ACTIVE

_binOps = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.div,
    ast.Mod: operator.mod
}


def arithmeticEval(s):
    """
    A safe eval supporting basic arithmetic operations.

    :param s: expression to evaluate
    :return: value
    """
    node = ast.parse(s, mode='eval')

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return _binOps[type(node.op)](_eval(node.left), _eval(node.right))
        else:
            raise Exception('Unsupported type {}'.format(node))

    return _eval(node.body)


class TimedDict(MutableMapping):
    """Acts like a normal dict, but keys will only remain in the dictionary for a specified time span."""
    def __init__(self, cache_time='5 minutes'):
        self.cache_time = parse_timedelta(cache_time)
        self._store = dict()

    def __getitem__(self, key):
        add_time, value = self._store[key]
        # Prune data and raise KeyError when expired
        if add_time < datetime.now() - self.cache_time:
            del self._store[key]
            raise KeyError(key, 'cache time expired')
        return value

    def __setitem__(self, key, value):
        self._store[key] = (datetime.now(), value)

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        # Uses our getitem to skip expired items
        return (key for key in self._store.keys() if key in self)

    def __len__(self):
        return len(list(self.__iter__()))

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, dict(zip(self._store, (v[1] for v in self._store.values()))))


class BufferQueue(Queue.Queue):
    """Used in place of a file-like object to capture text and access it safely from another thread."""
    # Allow access to the Empty error from here
    Empty = Queue.Empty

    def write(self, line):
        self.put(line)


def singleton(cls):
    instances = {}

    def getinstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return getinstance
