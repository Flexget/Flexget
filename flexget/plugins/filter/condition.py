""" Boolean Expression Filtering Plugins.
"""
import logging

#from flexget.feed import Entry
from flexget import plugin, validator

log = logging.getLogger(__name__.rsplit('.')[-1])


class ConditionPlugin(plugin.Plugin):
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
        parser = matching.ConditionParser(lambda _: {"matcher": matching.MagicFilter}, "title")
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

        from pyrocore.util.types import Bunch

        warnings = 0
        for entry in feed.entries:
            for check in conditions:
                try:
                    log.debugall("Applying %s to %r" % (check, entry))
                    if check(Bunch(entry)):
                        if matched:
                            matched(entry)
                        break
                except (TypeError, ValueError, AttributeError, matching.FilterError), exc:
                    log.debug("%s while applying %s to %r" % (exc, check, entry))
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


class RejectIf(ConditionPlugin):
    """ Reject items that match a condition.

        Example:
            reject_if:
              - imdb_score<6.2 imdb_year>2009
              - rotten_tomatoes<80
    """

    def on_feed_filter(self, feed, config):
        self.process(feed, config, matched=feed.reject)


class AcceptIf(ConditionPlugin):
    """ Accept items that match a condition.

        Example:
            accept_if: imdb_score>=8 OR year=2011
    """

    def on_feed_filter(self, feed, config):
        self.process(feed, config, matched=feed.accept)
