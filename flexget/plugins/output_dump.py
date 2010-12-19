from flexget.plugin import register_plugin, register_parser_option
import logging

log = logging.getLogger('dump')


def dump(entries, debug=False):
    """Dump :entries: to stdout"""
    for entry in entries:
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
                if debug:
                    print '%-15s: [not printable] (%s)' % (field, value)
        print ''


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

        undecided = [entry for entry in feed.entries if not entry in feed.accepted]
        if undecided:
            print '-- Undecided: --------------------------'
            dump(undecided, feed.manager.options.debug)
        if feed.accepted:
            print '-- Accepted: ---------------------------'
            dump(feed.accepted, feed.manager.options.debug)
        if feed.rejected:
            print '-- Rejected: ---------------------------'
            dump(feed.rejected, feed.manager.options.debug)

register_plugin(OutputDump, 'dump', builtin=True)
register_parser_option('--dump', action='store_true', dest='dump_entries', default=False, help='Display all feed entries')
