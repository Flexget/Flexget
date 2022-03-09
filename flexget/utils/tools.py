"""Contains miscellaneous helpers"""
import ast
import copy
import hashlib
import locale
import operator
import os
import queue
import re
import sys
import weakref
from collections import OrderedDict, defaultdict
from collections.abc import MutableMapping
from datetime import datetime, timedelta
from html.entities import name2codepoint
from pprint import pformat
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    Union,
)

import psutil
import requests
from loguru import logger

import flexget

if TYPE_CHECKING:
    from flexget.entry import Entry
    from flexget.task import Task

logger = logger.bind(name='utils')


def str_to_boolean(string: str) -> bool:
    return string.lower() in ['true', '1', 't', 'y', 'yes']


def str_to_int(string: str) -> Optional[int]:
    try:
        return int(string.replace(',', ''))
    except ValueError:
        return None


def convert_bytes(bytes_num: Union[int, float]) -> str:
    """Returns given bytes as prettified string."""

    bytes_num = float(bytes_num)
    units_prefixes = OrderedDict(
        {
            'T': 1099511627776,  # 1024 ** 4
            'G': 1073741824,  # 1024 ** 3
            'M': 1048576,  # 1024 ** 2
            'K': 1024,
        }
    )
    for unit, threshold in units_prefixes.items():
        if bytes_num > threshold:
            return f'{bytes_num/threshold:.2f}{unit}'
    return f'{bytes_num:.2f}b'


class MergeException(Exception):
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return repr(self.value)


def strip_html(text: str) -> str:
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


def _htmldecode(text: str) -> str:
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


def decode_html(value: str) -> str:
    """
    :param string value: String to be html-decoded
    :returns: Html decoded string
    """
    return _htmldecode(value)


def encode_html(unicode_data: str, encoding: str = 'ascii') -> bytes:
    """
    Encode unicode_data for use as XML or HTML, with characters outside
    of the encoding converted to XML numeric character references.
    """
    return unicode_data.encode(encoding, 'xmlcharrefreplace')


def merge_dict_from_to(d1: dict, d2: dict) -> None:
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
                    raise Exception(f'Unknown type: {type(v)} value: {repr(v)} in dictionary')
            elif isinstance(v, (str, bool, int, float, list, type(None))) and isinstance(
                d2[k], (str, bool, int, float, list, type(None))
            ):
                # Allow overriding of non-container types with other non-container types
                pass
            else:
                raise MergeException(
                    'Merging key %s failed, conflicting datatypes %r vs. %r.'
                    % (k, type(v).__name__, type(d2[k]).__name__)
                )
        else:
            d2[k] = copy.deepcopy(v)


class ReList(list):
    """
    A list that stores regexps.

    You can add compiled or uncompiled regexps to the list.
    It will always return the compiled version.
    It will compile the text regexps on demand when first accessed.
    """

    # Set the default flags
    flags = re.IGNORECASE

    def __init__(self, *args, **kwargs) -> None:
        """Optional :flags: keyword argument with regexp flags to compile with"""
        if 'flags' in kwargs:
            self.flags = kwargs.pop('flags')
        list.__init__(self, *args, **kwargs)

    def __getitem__(self, k) -> Pattern:  # type: ignore
        # Doesn't support slices. Do we care?
        item = list.__getitem__(self, k)
        if isinstance(item, str):
            item = re.compile(item, self.flags)
            self[k] = item
        return item

    def __iter__(self) -> Iterator[Pattern]:
        for i in range(len(self)):
            yield self[i]


# Determine the encoding for io
io_encoding = ''
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


def parse_timedelta(value: Union[timedelta, str, None]) -> timedelta:
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
        return timedelta(**params)  # type: ignore
    except TypeError:
        raise ValueError(f"Invalid time format '{value}'")


def multiply_timedelta(interval: timedelta, number: Union[int, float]) -> timedelta:
    """`timedelta`s can not normally be multiplied by floating points. This does that."""
    return timedelta(seconds=interval.total_seconds() * number)


def pid_exists(pid: int):
    try:
        return psutil.Process(pid).status() != psutil.STATUS_STOPPED
    except psutil.NoSuchProcess:
        return False


_binOps = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


class TimedDict(MutableMapping):
    """Acts like a normal dict, but keys will only remain in the dictionary for a specified time span."""

    _instances: Dict[int, 'TimedDict'] = weakref.WeakValueDictionary()

    def __init__(self, cache_time: Union[timedelta, str] = '5 minutes'):
        self.cache_time = parse_timedelta(cache_time)
        self._store: dict = {}
        self._last_prune = datetime.now()
        self._instances[id(self)] = self

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
            self.__class__.__name__,
            dict(list(zip(self._store, (v[1] for v in list(self._store.values()))))),
        )

    @classmethod
    def clear_all(cls):
        """
        Clears all instantiated TimedDicts.
        Used by tests to make sure artifacts don't leak between tests.
        """
        for store in cls._instances.values():
            store.clear()


class BufferQueue(queue.Queue):
    """Used in place of a file-like object to capture text and access it safely from another thread."""

    # Allow access to the Empty error from here
    Empty = queue.Empty

    def write(self, line):
        self.put(line)


class TitleYear(NamedTuple):
    title: str
    year: Optional[int]


def split_title_year(title: str) -> TitleYear:
    """Splits title containing a year into a title, year pair."""
    if not title:
        return TitleYear('', None)
    if not re.search(r'\d{4}', title):
        return TitleYear(title, None)
    # We only recognize years from the 2nd and 3rd millennium, FlexGetters from the year 3000 be damned!
    match = re.search(r'(.*?)\(?([12]\d{3})?\)?$', title)

    if not match:
        return TitleYear(title, None)
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
    return TitleYear(title, year)


def get_latest_flexget_version_number() -> Optional[str]:
    """
    Return latest Flexget version from https://pypi.python.org/pypi/FlexGet/json
    """
    try:
        data = requests.get('https://pypi.python.org/pypi/FlexGet/json').json()
        return data.get('info', {}).get('version')
    except requests.RequestException:
        return None


def get_current_flexget_version() -> str:
    return flexget.__version__


def parse_filesize(text_size: str, si: bool = True) -> float:
    """
    Parses a data size and returns its value in mebibytes

    :param string text_size: string containing the data size to parse i.e. "5 GB"
    :param bool si: If True, possibly ambiguous units like KB, MB, GB will be assumed to be base 10 units,
    rather than the default base 2. i.e. if si then 50 GB = 47684 else 50GB = 51200

    :returns: an float with the data size in mebibytes
    """
    prefix_order = {'': 0, 'k': 1, 'm': 2, 'g': 3, 't': 4, 'p': 5}

    parsed_size = re.match(
        r'(\d+(?:[.,\s]\d+)*)(?:\s*)((?:[ptgmk]i?)?b)', text_size.strip().lower(), flags=re.UNICODE
    )
    if not parsed_size:
        raise ValueError('%s does not look like a file size' % text_size)
    amount_str = parsed_size.group(1)
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
    amount = float(amount_str.replace(',', '').replace(' ', ''))
    base = 1000 if si else 1024
    return (amount * (base**order)) / 1024**2


def get_config_hash(config: Any) -> str:
    """
    :param dict config: Configuration
    :return: MD5 hash for *config*
    """
    if isinstance(config, dict) or isinstance(config, list):
        # this does in fact support nested dicts, they're sorted too!
        return hashlib.md5(pformat(config).encode('utf-8')).hexdigest()
    else:
        return hashlib.md5(str(config).encode('utf-8')).hexdigest()


def get_config_as_array(config: dict, key: str) -> list:
    """
    Return configuration key as array, even if given as a single string
    :param dict config: Configuration
    :param string key: Configuration
    :return: Array
    """
    v = config.get(key, [])
    if not isinstance(v, list):
        return [v]
    return v


def parse_episode_identifier(
    ep_id: Union[str, int], identify_season: bool = False
) -> Tuple[str, str]:
    """
    Parses series episode identifier, raises ValueError if it fails

    :param ep_id: Value to parse
    :return: Return identifier type: `sequence`, `ep` or `date`
    :raises ValueError: If ep_id does not match any valid types
    """
    error = None
    identified_by = ''
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
            error = f'`{ep_id}` is not a valid episode identifier.'
    if error:
        raise ValueError(error)
    return identified_by, entity_type


def group_entries(entries: Iterable['Entry'], identifier: str) -> Dict[str, List['Entry']]:
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


def aggregate_inputs(task: 'Task', inputs: List[dict]) -> List['Entry']:
    from flexget import plugin

    entries = []
    entry_titles = set()
    entry_urls = set()
    entry_locations = set()
    for item in inputs:
        for input_name, input_config in item.items():
            input = plugin.get_plugin_by_name(input_name)
            method = input.phase_handlers['input']
            try:
                result = method(task, input_config)
            except plugin.PluginError as e:
                logger.warning('Error during input plugin {}: {}', input_name, e)
                continue

            if not result:
                logger.warning('Input {} did not return anything', input_name)
                continue

            for entry in result:
                urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])

                if any(url in entry_urls for url in urls):
                    logger.debug('URL for `{}` already in entry list, skipping.', entry['title'])
                    continue

                if entry['title'] in entry_titles:
                    logger.debug(
                        'Ignored duplicate title `{}`', entry['title']
                    )  # TODO: should combine?
                    continue

                if entry.get('location') and entry['location'] in entry_locations:
                    logger.debug(
                        'Ignored duplicate location `{}`', entry['location']
                    )  # TODO: should combine?
                    continue

                entries.append(entry)
                entry_titles.add(entry['title'])
                entry_urls.update(urls)
                if entry.get('location'):
                    entry_locations.add(entry['location'])

    return entries


# Mainly used due to Too Many Variables error if we use too many variables at a time in the in_ clause.
# SQLite supports up to 999 by default. Ubuntu, Arch and macOS set this limit to 250,000 though, so it's a rare issue.
def chunked(seq: Sequence, limit: int = 900) -> Iterator[Sequence]:
    """Helper to divide our expired lists into sizes sqlite can handle in a query. (<1000)"""
    for i in range(0, len(seq), limit):
        yield seq[i : i + limit]
