from __future__ import absolute_import
import logging

log = logging.getLogger('utils.regex')


regex_module = 're'

try:
    from regexe import *
except ImportError:
    from re import *
    # This flag is not included in re.__all__
    from re import DEBUG
    log.debug('Using stdlib `re` module for regex')
else:
    regex_module = 'regex'
    log.debug('Using `regex` module for regex')
    # Ensure we are in the backwards compatible mode by default
    import regex as _regex
    _regex.DEFAULT_VERSION = _regex.VERSION0
