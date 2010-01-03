from optparse import SUPPRESS_HELP
from flexget.plugin import *


class YamlDump:
    """
        Dummy plugin for testing, outputs all entries in yaml
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_output(self, feed):
        if not 'dump' in feed.config and not feed.manager.options.dump:
            return
        #from flexget.utils.tools import sanitize
        import yaml
        
        def dump(values):
            for entry in values:
                #c = entry.copy()
                #sanitize(c)
                #print yaml.safe_dump(entry)
                print entry
                
        if feed.entries:
            print '-- Entries: ----------------------------'
            dump(feed.entries)
        if feed.accepted:
            print '-- Accepted: ---------------------------'
            dump(feed.accepted)
        if feed.rejected:
            print '-- Rejected: ---------------------------'
            dump(feed.rejected)
            
register_plugin(YamlDump, 'dump', builtin=True)

# for some fucking reason this --dump does not work
register_parser_option('--dump', action='store_true', dest='dump', default=False, help=SUPPRESS_HELP)
