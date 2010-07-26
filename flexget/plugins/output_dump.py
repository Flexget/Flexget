from optparse import SUPPRESS_HELP
from flexget.plugin import *
import logging

log = logging.getLogger('dump')


class OutputDump(object):
    """
        Dummy plugin for testing, outputs all entries to stdout
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_output(self, feed):
        if not 'dump' in feed.config and not feed.manager.options.dump_entries:
            return
        #from flexget.utils.tools import sanitize
        #import yaml
        
        def dump(values):
            for entry in values:
                #c = entry.copy()
                #sanitize(c)
                #print yaml.safe_dump(entry)
                for field in entry:
                    value = entry[field]
                    if isinstance(value, basestring):
                        print '%-15s: %s' % (field, value.replace('\r', '').replace('\n', ''))
                    elif isinstance(value, int) or isinstance(value, float):
                        print '%-15s: %s' % (field, value)
                    else:
                        print '%-15s: [not printable]' % (field, value)
                print ''
                
        if feed.entries:
            print '-- Entries: ----------------------------'
            dump(feed.entries)
        if feed.accepted:
            print '-- Accepted: ---------------------------'
            dump(feed.accepted)
        if feed.rejected:
            print '-- Rejected: ---------------------------'
            dump(feed.rejected)
            
register_plugin(OutputDump, 'dump', builtin=True)
register_parser_option('--dump', action='store_true', dest='dump_entries', default=False, help=SUPPRESS_HELP)
