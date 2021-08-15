"""
Helper module that can load whatever version of the json module is available.
Plugins can just import the methods from this module.

Also allows date and datetime objects to be encoded/decoded.
"""
import datetime
from collections.abc import Iterable, Mapping
from contextlib import suppress
from typing import Union, Any

from flexget.plugin import DependencyError

try:
    import simplejson as json
except ImportError:
    try:
        import json  # type: ignore  # python/mypy#1153
    except ImportError:
        try:
            # Google Appengine offers simplejson via django
            from django.utils import simplejson as json  # type: ignore
        except ImportError:
            raise DependencyError(missing='simplejson')

DATE_FMT = '%Y-%m-%d'
ISO8601_FMT = '%Y-%m-%dT%H:%M:%SZ'


class DTDecoder(json.JSONDecoder):
    def decode(self, obj, **kwargs):
        # The built-in `json` library will `unicode` strings, except for empty strings. patch this for
        # consistency so that `unicode` is always returned.
        if obj == b'':
            return ''

        if isinstance(obj, str):
            dt_str = obj.strip('"')
            try:
                return datetime.datetime.strptime(dt_str, ISO8601_FMT)
            except (ValueError, TypeError):
                with suppress(ValueError, TypeError):
                    return datetime.datetime.strptime(dt_str, DATE_FMT)

        return super().decode(obj, **kwargs)


def _datetime_encoder(obj: Union[datetime.datetime, datetime.date]) -> str:
    if isinstance(obj, datetime.datetime):
        return obj.strftime(ISO8601_FMT)
    elif isinstance(obj, datetime.date):
        return obj.strftime(DATE_FMT)
    raise TypeError


def _datetime_decoder(dict_: dict) -> dict:
    for key, value in dict_.items():
        # The built-in `json` library will `unicode` strings, except for empty strings. patch this for
        # consistency so that `unicode` is always returned.
        if value == b'':
            dict_[key] = ''
            continue

        try:
            datetime_obj = datetime.datetime.strptime(value, ISO8601_FMT)
            dict_[key] = datetime_obj
        except (ValueError, TypeError):
            with suppress(ValueError, TypeError):
                date_obj = datetime.datetime.strptime(value, DATE_FMT)
                dict_[key] = date_obj.date()

    return dict_


def _empty_unicode_decoder(dict_: dict) -> dict:
    for key, value in dict_.items():
        # The built-in `json` library will `unicode` strings, except for empty strings. patch this for
        # consistency so that `unicode` is always returned.
        if value == b'':
            dict_[key] = ''
    return dict_


def dumps(*args, **kwargs) -> str:
    if kwargs.pop('encode_datetime', False):
        kwargs['default'] = _datetime_encoder
    return json.dumps(*args, **kwargs)


def dump(*args, **kwargs) -> None:
    if kwargs.pop('encode_datetime', False):
        kwargs['default'] = _datetime_encoder
    return json.dump(*args, **kwargs)


def loads(*args, **kwargs) -> Any:
    """
    :param bool decode_datetime: If `True`, dates in ISO8601 format will be deserialized to :class:`datetime.datetime`
      objects.
    """
    if kwargs.pop('decode_datetime', False):
        kwargs['object_hook'] = _datetime_decoder
        kwargs['cls'] = DTDecoder
    else:
        kwargs['object_hook'] = _empty_unicode_decoder
    return json.loads(*args, **kwargs)


def load(*args, **kwargs) -> Any:
    """
    :param bool decode_datetime: If `True`, dates in ISO8601 format will be deserialized to :class:`datetime.datetime`
      objects.
    """
    if kwargs.pop('decode_datetime', False):
        kwargs['object_hook'] = _datetime_decoder
        kwargs['cls'] = DTDecoder
    else:
        kwargs['object_hook'] = _empty_unicode_decoder
    return json.load(*args, **kwargs)


def coerce(obj) -> Union[str, int, float, bool, dict, list, None]:
    """
    Coerce a data structure to a JSON serializable form.

    Will recursively go through data structure, and attempt to turn anything not JSON serializable into a string.
    """
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, datetime.datetime):
        return obj.strftime(ISO8601_FMT)
    if isinstance(obj, datetime.date):
        return obj.strftime(DATE_FMT)
    if isinstance(obj, Mapping):
        return {k: coerce(v) for k, v in obj.items()}
    if isinstance(obj, Iterable):
        return [coerce(v) for v in obj]
    try:
        return str(obj)
    except Exception:
        return 'NOT JSON SERIALIZABLE'
