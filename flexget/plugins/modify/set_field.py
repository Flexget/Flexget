from copy import copy
from datetime import datetime, date, time
from email.utils import parsedate
from time import mktime
import os
import re
import sys
import logging
from flexget.plugin import register_plugin, priority
from flexget.utils.tools import replace_from_entry

log = logging.getLogger('set')
jinja = False


def filter_pathbase(val):
    """Base name of a path."""
    return os.path.basename(val or '')


def filter_pathname(val):
    """Base name of a path, without its extension."""
    return os.path.splitext(os.path.basename(val or ''))[0]


def filter_pathext(val):
    """Extension of a path (including the '.')."""
    return os.path.splitext(val or '')[1]


def filter_pathdir(val):
    """Directory containing the given path."""
    return os.path.dirname(val or '')


def filter_pathscrub(val, ascii=False, windows=None):
    """Replace problematic characters in a path."""
    if windows is None:
        windows = sys.platform.startswith("win")
    if ascii:
        repl = {'"': '`', "'": '`'}
        if windows:
            repl.update({':': ';', '?': '_'})
    else:
        repl = {'"': u'\u201d', "'": u'\u2019'}
        if windows:
            repl.update({':': u'\u02d0', '?': u'\u061f'})

    return re.sub('[%s]' % ''.join(repl), lambda i: repl[i.group(0)], val or '')


def filter_re_replace(val, pattern, repl):
    """Perform a regexp replacement on the given string."""
    return re.sub(pattern, repl, unicode(val))


def filter_re_search(val, pattern):
    """Perform a search for given regexp pattern, return the matching portion of the text."""
    if not isinstance(val, basestring):
        return val
    result = re.search(pattern, val)
    if result:
        i = result.group(0)
        return result.group(0)
    return ''


def filter_formatdate(val, format):
    """Returns a string representation of a datetime object according to format string."""
    if not isinstance(val, (datetime, date, time)):
        return val
    return val.strftime(format)


def filter_parsedate(val):
    """Attempts to parse a date according to the rules in RFC 2822"""
    return datetime.fromtimestamp(mktime(parsedate(val)))


class ModifySet(object):

    """Allows adding information to a feed entry for use later.

    Example:

    set:
      path: ~/download/path/
    """

    def __init__(self):
        self.keys = {}
        try:
            from jinja2 import Environment
        except ImportError:
            self.jinja = False
        else:
            self.jinja = True

    def validator(self):
        from flexget import validator
        v = validator.factory('dict')
        v.accept_any_key('any')
        return v

    def register_key(self, key, type='text'):
        """
        plugins can call this method to register set keys as valid
        """
        if key:
            if not key in self.keys:
                self.keys[key] = type

    def register_keys(self, keys):
        """
        for easy registration of multiple keys
        """
        for key, value in keys.iteritems():
            self.register_key(key, value)

    def on_feed_start(self, feed, config):
        """Checks that jinja2 is available"""
        if not self.jinja:
            log.warning("jinja2 module is not available, set plugin will only work with python string replacement.")

    # Filter priority is -255 so we run after all filters are finished
    @priority(-255)
    def on_feed_filter(self, feed, config):
        """
        Adds the set dict to all accepted entries. This is not really a filter plugin,
        but it needs to be run before feed_download, so it is run last in the filter chain.
        """
        for entry in feed.entries:
            self.modify(entry, config, False, entry in feed.accepted)

    def modify(self, entry, config, validate=False, errors=True):
        """
        this can be called from a plugin to add set values to an entry
        """
        # Create a new dict so we don't overwrite the set config with string replaced values.
        conf = copy(config)

        # If jinja2 is available do template replacement
        if self.jinja:
            from jinja2 import Environment, StrictUndefined, UndefinedError
            env = Environment(undefined=StrictUndefined)
            env.filters.update((name.split('_', 1)[1], filt)
                for name, filt in globals().items()
                if name.startswith("filter_"))

            for field, template_string in conf.items():
                if isinstance(template_string, basestring):
                    template = env.from_string(template_string)
                    variables = {'now': datetime.now()}
                    variables.update(entry)
                    try:
                        result = template.render(variables)
                    except UndefinedError, e:
                        # If the replacement failed, remove this key from the update dict
                        log.debug('%s did not have the required fields for jinja2 template: %s' % (entry['title'], e))
                        del conf[field]
                    else:
                        conf[field] = result

        # Do string replacement
        for field, value in conf.items():
            if isinstance(value, basestring):
                logger = log.error if errors else log.debug
                result = replace_from_entry(value, entry, field, logger, default=None)
                if result is None:
                    # If the replacement failed, remove this key from the update dict
                    del conf[field]
                else:
                    conf[field] = result

        if validate:
            from flexget import validator
            v = validator.factory('dict')
            for key in self.keys:
                v.accept(self.keys[key], key=key)

            if not v.validate(config):
                log.info('set parameters are invalid, error follows')
                log.info(v.errors.messages)
                return

        # If there are valid items in the config, apply to entry.
        if conf:
            log.debug('adding set: info to entry:\'%s\' %s' % (entry['title'], conf))
            entry.update(conf)

register_plugin(ModifySet, 'set', api_ver=2)
