""" Boolean Expression Filtering Plugins.
"""
import logging

from flexget import plugin, validator

log = logging.getLogger(__name__.rsplit('.')[-1])


class AttributeAccessor(object):
    """ Wrapper for entries that allows deep field access by 
        either the dict or the object protocol.
    """
    
    def __init__(self, obj):
        self.obj = obj

    def _getfield(self, key, lookup_error):
        fullname = key # store for logging
        obj = self.obj

        while key is not None:
            try:
                name, key = key.split('.', 1)
            except ValueError:
                name, key = key, None
            optional = name.startswith('?')
            if optional:
                name = name[1:]

            try:
                obj = obj[name]
            except (TypeError, KeyError):
                try:
                    obj = getattr(obj, name)
                except AttributeError, exc:
                    if optional:
                        log.debugall("AttributeAccessor: ?%s[.%s] ==> None" % (name, key))
                        return None
                    if name != fullname:
                        raise lookup_error("%s while trying to access %s" % (exc, fullname))
                    else:
                        raise lookup_error(str(exc))
            log.debugall("AttributeAccessor: %s[.%s] ==> %.200s..." % (name, key, repr(obj)))

        return obj

    def __getitem__(self, name):
        return self._getfield(name, KeyError)

    def __getattr__(self, name):
        return self._getfield(name, AttributeError)


class ConditionPluginBase(plugin.Plugin):
    """ Base class for condition filter plugins.
    """

    def validator(self):
        """ Return validator suitable for filter conditions.
        """
        root = validator.factory()
        root.accept("list").accept("text") # list of conditions ORed together
        root.accept("text") # a single condition
        return root

    def parse(self, config):
        """ Parse filter condition(s) from config.
        """
        try:
            from pyrocore.util import matching
        except ImportError, exc:
            raise plugin.DependencyError("You need to (easy_)install 'pyrocore>=0.4' to use the %s plugin (%s)" % (
                self.plugin_info.name, exc))

        if isinstance(config, basestring):
            config = [config]        
        conditions = []
        parser = matching.ConditionParser(matching.ConditionParser.AMENABLE, 
            default_field="title", ident_re=r"(?:\??[_A-Za-z0-9]+\.?)*\??[_A-Za-z0-9]+")
        for cond in config:
            try:
                conditions.append(parser.parse(cond))
            except matching.FilterError, exc:
                raise plugin.PluginError(str(exc))

        log.debug("%s: %s" % (self.plugin_info.name, " OR ".join(str(i) for i in conditions)))
        return conditions, matching

    def process(self, feed, config, matched=None, failed=None):
        """ Apply config condition to all items and depending on the outcome,
            call either matched or failed with them.
            
            @param feed: The feed to process. 
            @param config: Condition. 
            @param matched: Callable applied to items that fulfill the condition. 
            @param failed: Callable applied to items that fail the condition. 
        """
        conditions, matching = self.parse(config)

        warnings = 0
        for entry in feed.entries:
            wrapped_entry = AttributeAccessor(entry)
            for check in conditions:
                try:
                    truth = check(wrapped_entry)
                    log.debugall("%r from applying %s to %r" % (truth, check, entry))
                    if truth:
                        if matched:
                            matched(entry)
                        break
                except (TypeError, ValueError, AttributeError, matching.FilterError), exc:
                    log.debug("%s:%s while applying %s to %r" % (type(exc).__name__, exc, check, entry))
                    if not warnings:
                        log.warning("Condition filtering problem: %s" % (exc,))
                    warnings += 1
                    continue # error => try next condition
            else:
                # None of the conditions triggered
                if failed:
                    failed(entry)

        if warnings > 1:
            log.warning("%d problems encountered during processing %d entries" % (warnings, len(feed.entries)))


class RejectIf(ConditionPluginBase):
    """ Reject items that match a condition.

        Example:
            reject_if:
              - imdb_score<6.2 imdb_year>2009
              - rotten_tomatoes<80
    """

    def on_feed_filter(self, feed, config):
        """ Reject entries meeting any of the given conditions.
        """
        self.process(feed, config, matched=feed.reject)


class AcceptIf(ConditionPluginBase):
    """ Accept items that match a condition.

        Example:
            accept_if: imdb_score>=8 OR year=2011
    """

    def on_feed_filter(self, feed, config):
        """ Accept entries meeting any of the given conditions.
        """
        self.process(feed, config, matched=feed.accept)


class RejectIfDownload(ConditionPluginBase):
    """ Reject downloaded items that match a condition.

        Example:
            reject_if_download: ?torrent.content.info.?private=1
    """

    @plugin.priority(64)
    def on_feed_modify(self, feed, config):
        """ Reject entries meeting any of the given conditions.
        """
        self.process(feed, config, matched=feed.reject)


class AcceptIfDownload(ConditionPluginBase):
    """ Accept downloaded items that match a condition.

        Example:
            # Accept by tracker
            accept_if_download: ?torrent.content.announce=*ubuntu.com[:/]*
    """

    @plugin.priority(64)
    def on_feed_modify(self, feed, config):
        """ Accept entries meeting any of the given conditions.
        """
        self.process(feed, config, matched=feed.accept)
