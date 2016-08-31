from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import argparse
import functools
import logging

from flexget import options
from flexget.event import event

log = logging.getLogger('cli_config')

"""
Allows specifying yml configuration values from commandline parameters.

Yml variables are prefixed with dollar sign ($).
Commandline parameter must be comma separated list of variable=values.

Configuration example::

  tasks:
    my task:
      rss: $url
      download: $path

Commandline example::

  --cli-config url=http://some.url/ path=~/downloads

"""


def replace_in_item(replaces, item):
    replace = functools.partial(replace_in_item, replaces)
    if isinstance(item, basestring):
        # Do replacement in text objects
        for key, val in replaces.items():
            item = item.replace('$%s' % key, val)
        return item
    elif isinstance(item, list):
        # Make a new list with replacements done on each item
        return list(map(replace, item))
    elif isinstance(item, dict):
        # Make a new dict with replacements done on keys and values
        return dict(list(map(replace, kv_pair)) for kv_pair in item.items())
    else:
        # We don't know how to do replacements on this item, just return it
        return item


@event('manager.before_config_validate')
def substitute_cli_variables(config, manager):
    if not manager.options.execute.cli_config:
        return
    return replace_in_item(dict(manager.options.execute.cli_config), config)


def key_value_pair(text):
    if '=' not in text:
        raise argparse.ArgumentTypeError('arguments must be in VARIABLE=VALUE form')
    return text.split('=', 1)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--cli-config', nargs='+', type=key_value_pair, metavar='VARIABLE=VALUE',
                                               help='configuration parameters through commandline')
