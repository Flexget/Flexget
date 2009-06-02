import yaml

class YamlDump:

    """
        Dummy plugin for testing, outputs all entries in yaml
    """

    def register(self, manager, parser):
        from optparse import SUPPRESS_HELP
        manager.register('dump', debug_plugin=True, builtin=True)
        parser.add_option('--dump', action='store_true', dest='dump', default=0,
                          help=SUPPRESS_HELP)
        
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
