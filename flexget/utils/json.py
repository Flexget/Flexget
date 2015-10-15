"""
Helper module that can load whatever version of the json module is available.
Plugins can just import the methods from this module.

Also allows date and datetime objects to be encoded/decoded.
"""
from __future__ import unicode_literals, division, absolute_import
import datetime

from flexget.plugin import DependencyError

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        try:
            # Google Appengine offers simplejson via django
            from django.utils import simplejson as json
        except ImportError:
            raise DependencyError(missing='simplejson')


DATE_FMT = '%Y-%m-%d'
ISO8601_FMT = '%Y-%m-%dT%H:%M:%SZ'


def _datetime_encoder(obj):
    if isinstance(obj, datetime.datetime):
        return obj.strftime(ISO8601_FMT)
    elif isinstance(obj, datetime.date):
        return obj.strftime(DATE_FMT)
    raise TypeError


def _datetime_decoder(dict_):
    for key, value in dict_.iteritems():
        # The built-in `json` library will `unicode` strings, except for empty strings. patch this for
        # consistency so that `unicode` is always returned.
        if value == b'':
            dict_[key] = ''
            continue

        try:
            datetime_obj = datetime.datetime.strptime(value, ISO8601_FMT)
            dict_[key] = datetime_obj
        except (ValueError, TypeError):
            try:
                date_obj = datetime.datetime.strptime(value, DATE_FMT)
                dict_[key] = date_obj.date()
            except (ValueError, TypeError):
                continue

    return dict_


def _empty_unicode_decoder(dict_):
    for key, value in dict_.iteritems():
        # The built-in `json` library will `unicode` strings, except for empty strings. patch this for
        # consistency so that `unicode` is always returned.
        if value == b'':
            dict_[key] = ''
            continue
    return dict_


def dumps(*args, **kwargs):
    if kwargs.pop('encode_datetime', False):
        kwargs['default'] = _datetime_encoder
    return json.dumps(*args, **kwargs)


def dump(*args, **kwargs):
    if kwargs.pop('encode_datetime', False):
        kwargs['default'] = _datetime_encoder
    return json.dump(*args, **kwargs)


def loads(*args, **kwargs):
    """
    :param bool decode_datetime: If `True`, dates in ISO8601 format will be deserialized to :class:`datetime.datetime`
      objects.
    """
    if kwargs.pop('decode_datetime', False):
        kwargs['object_hook'] = _datetime_decoder
    else:
        kwargs['object_hook'] = _empty_unicode_decoder
    return json.loads(*args, **kwargs)


def load(*args, **kwargs):
    """
    :param bool decode_datetime: If `True`, dates in ISO8601 format will be deserialized to :class:`datetime.datetime`
      objects.
    """
    if kwargs.pop('decode_datetime', False):
        kwargs['object_hook'] = _datetime_decoder
    else:
        kwargs['object_hook'] = _empty_unicode_decoder
    return json.load(*args, **kwargs)
