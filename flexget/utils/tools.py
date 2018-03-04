"""Contains miscellaneous helpers"""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib import request
from future.utils import PY2

import logging
import ast
import copy
import hashlib
import locale
import operator
import os
import re
import sys
from collections import MutableMapping, defaultdict
from datetime import timedelta, datetime
from pprint import pformat

import flexget
import queue
import requests
from html.entities import name2codepoint

log = logging.getLogger('utils')


def str_to_boolean(string):
    return string.lower() in ['true', '1', 't', 'y', 'yes']


def str_to_int(string):
    try:
        return int(string.replace(',', ''))
    except ValueError:
        return None


if PY2:
    def native_str_to_text(string, **kwargs):
        if 'encoding' not in kwargs:
            kwargs['encoding'] = 'ascii'
        return string.decode(**kwargs)
else:
    def native_str_to_text(string, **kwargs):
        return string


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
    except Exception:
        return text


# This pattern matches a character entity reference (a decimal numeric
# references, a hexadecimal numeric reference, or a named reference).
charrefpat = re.compile(r'&(#(\d+|x[\da-fA-F]+)|[\w.:-]+);?')


def _htmldecode(text):
    """Decode HTML entities in the given text."""
    # From screpe.py - licensed under apache 2.0 .. should not be a problem for a MIT afaik
    if isinstance(text, str):
        uchr = chr
    else:
        def uchr(value):
            value > 127 and chr(value) or chr(value)

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
            if isinstance(v, type(d2[k])):
                if isinstance(v, dict):
                    merge_dict_from_to(d1[k], d2[k])
                elif isinstance(v, list):
                    d2[k].extend(copy.deepcopy(v))
                elif isinstance(v, (str, bool, int, float, type(None))):
                    pass
                else:
                    raise Exception('Unknown type: %s value: %s in dictionary' % (type(v), repr(v)))
            elif (isinstance(v, (str, bool, int, float, type(None))) and
                      isinstance(d2[k], (str, bool, int, float, type(None)))):
                # Allow overriding of non-container types with other non-container types
                pass
            else:
                raise MergeException('Merging key %s failed, conflicting datatypes %r vs. %r.' % (
                    k, type(v).__name__, type(d2[k]).__name__))
        else:
            d2[k] = copy.deepcopy(v)


class SmartRedirectHandler(request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        result = request.HTTPRedirectHandler.http_error_301(self, req, fp, code, msg, headers)
        result.status = code
        return result

    def http_error_302(self, req, fp, code, msg, headers):
        result = request.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        result.status = code
        return result


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
        if isinstance(item, str):
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


def timedelta_total_seconds(td):
    """replaces python 2.7+ timedelta.total_seconds()"""
    # TODO: Remove this when we no longer support python 2.6
    try:
        return td.total_seconds()
    except AttributeError:
        return (td.days * 24 * 3600) + td.seconds + (td.microseconds / 1000000)


def multiply_timedelta(interval, number):
    """`timedelta`s can not normally be multiplied by floating points. This does that."""
    return timedelta(seconds=timedelta_total_seconds(interval) * number)


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
    ast.Div: operator.truediv,
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
        self._last_prune = datetime.now()

    def _prune(self):
        """Prune all expired keys."""
        for key, (add_time, _) in list(self._store.items()):
            if add_time < datetime.now() - self.cache_time:
                del self._store[key]
        self._last_prune = datetime.now()

    def __getitem__(self, key):
        add_time, value = self._store[key]
        # Prune data and raise KeyError if expired
        if add_time < datetime.now() - self.cache_time:
            del self._store[key]
            raise KeyError(key, 'cache time expired')
        return value

    def __setitem__(self, key, value):
        # Make sure we clear periodically, even if old keys aren't accessed again
        if self._last_prune < datetime.now() - (2 * self.cache_time):
            self._prune()
        self._store[key] = (datetime.now(), value)

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        # Uses our getitem to skip expired items
        return (key for key in list(self._store.keys()) if key in self)

    def __len__(self):
        return len(list(self.__iter__()))

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__, dict(list(zip(self._store, (v[1] for v in list(self._store.values()))))))


class BufferQueue(queue.Queue):
    """Used in place of a file-like object to capture text and access it safely from another thread."""
    # Allow access to the Empty error from here
    Empty = queue.Empty

    def write(self, line):
        self.put(line)


def singleton(cls):
    instances = {}

    def getinstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return getinstance


def split_title_year(title):
    """Splits title containing a year into a title, year pair."""
    if not title:
        return
    if not re.search(r'\d{4}', title):
        return title, None
    match = re.search(r'(.*?)\(?(\d{4})?\)?$', title)

    title = match.group(1).strip()
    year_match = match.group(2)

    if year_match and not title:
        # title looks like a year, '2020' for example
        title = year_match
        year = None
    elif title and not year_match:
        year = None
    else:
        year = int(year_match)
    return title, year


def get_latest_flexget_version_number():
    """
    Return latest Flexget version from https://pypi.python.org/pypi/FlexGet/json
    """
    try:
        data = requests.get('https://pypi.python.org/pypi/FlexGet/json').json()
        return data.get('info', {}).get('version')
    except requests.RequestException:
        return


def get_current_flexget_version():
    return flexget.__version__


def parse_filesize(text_size, si=True):
    """
    Parses a data size and returns its value in mebibytes

    :param string text_size: string containing the data size to parse i.e. "5 GB"
    :param bool si: If True, possibly ambiguous units like KB, MB, GB will be assumed to be base 10 units,
    rather than the default base 2. i.e. if si then 50 GB = 47684 else 50GB = 51200

    :returns: an float with the data size in mebibytes
    """
    prefix_order = {'': 0, 'k': 1, 'm': 2, 'g': 3, 't': 4, 'p': 5}

    parsed_size = re.match('(\d+(?:[.,\s]\d+)*)(?:\s*)((?:[ptgmk]i?)?b)', text_size.strip().lower(), flags=re.UNICODE)
    if not parsed_size:
        raise ValueError('%s does not look like a file size' % text_size)
    amount = parsed_size.group(1)
    unit = parsed_size.group(2)
    if not unit.endswith('b'):
        raise ValueError('%s does not look like a file size' % text_size)
    unit = unit.rstrip('b')
    if unit.endswith('i'):
        si = False
        unit = unit.rstrip('i')
    if unit not in prefix_order:
        raise ValueError('%s does not look like a file size' % text_size)
    order = prefix_order[unit]
    amount = float(amount.replace(',', '').replace(' ', ''))
    base = 1000 if si else 1024
    return (amount * (base ** order)) / 1024 ** 2


def get_config_hash(config):
    """
    :param dict config: Configuration
    :return: MD5 hash for *config*
    """
    if isinstance(config, dict) or isinstance(config, list):
        # this does in fact support nested dicts, they're sorted too!
        return hashlib.md5(pformat(config).encode('utf-8')).hexdigest()
    else:
        return hashlib.md5(str(config).encode('utf-8')).hexdigest()


def get_config_as_array(config, key):
    """
    Return configuration key as array, even if given as a single string
    :param dict config: Configuration
    :param string key: Configuration
    :return: Array
    """
    v = config.get(key, [])
    if isinstance(v, str):
        return [v]
    return v


def parse_episode_identifier(ep_id, identify_season=False):
    """
    Parses series episode identifier, raises ValueError if it fails

    :param ep_id: Value to parse
    :return: Return identifier type: `sequence`, `ep` or `date`
    :raises ValueError: If ep_id does not match any valid types
    """
    error = None
    identified_by = None
    entity_type = 'episode'
    if isinstance(ep_id, int):
        if ep_id <= 0:
            error = 'sequence type episode must be higher than 0'
        identified_by = 'sequence'
    elif re.match(r'(?i)^S\d{1,4}E\d{1,3}$', ep_id):
        identified_by = 'ep'
    elif re.match(r'(?i)^S\d{1,4}$', ep_id) and identify_season:
        identified_by = 'ep'
        entity_type = 'season'
    elif re.match(r'\d{4}-\d{2}-\d{2}', ep_id):
        identified_by = 'date'
    else:
        # Check if a sequence identifier was passed as a string
        try:
            ep_id = int(ep_id)
            if ep_id <= 0:
                error = 'sequence type episode must be higher than 0'
            identified_by = 'sequence'
        except ValueError:
            error = '`%s` is not a valid episode identifier.' % ep_id
    if error:
        raise ValueError(error)
    return (identified_by, entity_type)


def group_entries(entries, identifier):
    from flexget.utils.template import RenderError

    grouped_entries = defaultdict(list)

    # Group by Identifier
    for entry in entries:
        try:
            rendered_id = entry.render(identifier)
        except RenderError:
            continue
        if not rendered_id:
            continue
        grouped_entries[rendered_id.lower().strip()].append(entry)

    return grouped_entries


def aggregate_inputs(task, inputs):
    from flexget import plugin

    entries = []
    entry_titles = set()
    entry_urls = set()
    entry_locations = set()
    for item in inputs:
        for input_name, input_config in item.items():
            input = plugin.get_plugin_by_name(input_name)
            if input.api_ver == 1:
                raise plugin.PluginError('Plugin %s does not support API v2' % input_name)
            method = input.phase_handlers['input']
            try:
                result = method(task, input_config)
            except plugin.PluginError as e:
                log.warning('Error during input plugin %s: %s', input_name, e)
                continue

            if not result:
                log.warning('Input %s did not return anything', input_name)
                continue

            for entry in result:
                urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])

                if any(url in entry_urls for url in urls):
                    log.debug('URL for `%s` already in entry list, skipping.', entry['title'])
                    continue

                if entry['title'] in entry_titles:
                    log.debug('Ignored duplicate title `%s`', entry['title'])  # TODO: should combine?
                    continue

                if entry.get('location') and entry['location'] in entry_locations:
                    log.debug('Ignored duplicate location `%s`', entry['location'])  # TODO: should combine?
                    continue

                entries.append(entry)
                entry_titles.add(entry['title'])
                entry_urls.update(urls)
                if entry.get('location'):
                    entry_locations.add(entry['location'])

    return entries


# Mainly used due to Too Many Variables error if we use too many variables at a time in the in_ clause.
# SQLite supports up to 999 by default. Ubuntu, Arch and macOS set this limit to 250,000 though, so it's a rare issue.
def chunked(seq, limit=900):
    """Helper to divide our expired lists into sizes sqlite can handle in a query. (<1000)"""
    for i in range(0, len(seq), limit):
        yield seq[i:i + limit]
