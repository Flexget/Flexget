from flexget.plugin import register_plugin, register_parser_option, priority
import logging
from flexget.utils.tools import console

log = logging.getLogger('dump')


def dump(entries, debug=False, eval_lazy=False):
    """
    Dump *entries* to stdout

    :param list entries: Entries to be dumped.
    :param bool debug: Print non printable fields as well.
    :param bool eval_lazy: Evaluate lazy fields.
    """

    invalid = object()
    for entry in entries:
        #c = entry.copy()
        #sanitize(c)
        #print yaml.safe_dump(entry)
        for field in entry:
            value = invalid
            if entry.is_lazy(field):
                if eval_lazy:
                    value = entry[field]
                else:
                    value = '<LazyField - value will be determined when it\'s accessed>'
            else:
                value = entry[field]
            assert value is not invalid
            if isinstance(value, basestring):
                try:
                    console('%-17s: %s' % (field, value.replace('\r', '').replace('\n', '')))
                except:
                    console('%-17s: %s (warning: unable to print)' % (field, repr(value)))
            elif isinstance(value, (int, float, list, dict)):
                console('%-17s: %s' % (field, value))
            elif value is None:
                console('%-17s: %s' % (field, value))
            else:
                if debug:
                    console('%-17s: [not printable] (%s)' % (field, value))
        console('')


class OutputDump(object):
    """
    Outputs all entries to console
    """

    params = None

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @staticmethod
    def optik(option, opt, value, parser):
        if parser.rargs:
            OutputDump.params = parser.rargs[0]
        else:
            OutputDump.params = True

    @priority(0)
    def on_feed_output(self, feed):
        if not 'dump' in feed.config and not OutputDump.params:
            return
        #from flexget.utils.tools import sanitize
        #import yaml

        eval_lazy = OutputDump.params == 'eval'
        undecided = [entry for entry in feed.entries if not entry in feed.accepted]
        if undecided:
            console('-- Undecided: --------------------------')
            dump(undecided, feed.manager.options.debug, eval_lazy)
        if feed.accepted:
            console('-- Accepted: ---------------------------')
            dump(feed.accepted, feed.manager.options.debug, eval_lazy)
        if feed.rejected:
            console('-- Rejected: ---------------------------')
            dump(feed.rejected, feed.manager.options.debug, eval_lazy)

register_plugin(OutputDump, 'dump', builtin=True)
#register_parser_option('--dump', action='store_true', dest='dump_entries', default=False,
#                       help='Display all feed entries')

register_parser_option('--dump', action='callback', callback=OutputDump.optik,
                       help='Display all entries in feed with details. '
                            'Arg `--dump eval` will evaluate all lazy fields.')
