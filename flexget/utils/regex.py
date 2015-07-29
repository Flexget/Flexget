from __future__ import absolute_import
import logging

log = logging.getLogger('utils.regex')


try:
    from regex import *
except ImportError:
    from re import *
    log.debug('Using stdlib `re` module for regex')
else:
    log.debug('Using `regex` module for regex')
    # Ensure we are in the backwards compatible mode by default
    import regex as _regex
    _regex.DEFAULT_VERSION = _regex.VERSION0
