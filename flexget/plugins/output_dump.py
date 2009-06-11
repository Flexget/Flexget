import yaml
from optparse import SUPPRESS_HELP

class YamlDump:

    """
        Dummy plugin for testing, outputs all entries in yaml
    """

    __plugin__ = 'dump'
    __parser_options__ = [
        (
            ['--dump'],
            dict(action='store_true', dest='dump', default=0, help=SUPPRESS_HELP)
        )
    ]

    def validator(self):
        from flexget import validator
        return validator.factory('any')

    def feed_output(self, feed):
        if not 'dump' in feed.config and not feed.manager.options.dump:
            return
        from flexget.utils.tools import sanitize
        def dump(values):
            for entry in values:
                c = entry.copy()
                sanitize(c)
                print yaml.safe_dump(c)
        if feed.accepted:
            print '-- Accepted: ---------------------------'
            dump(feed.accepted)
        if feed.rejected:
            print '-- Rejected: ---------------------------'
            dump(feed.rejected)
