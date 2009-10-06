import logging
from flexget.plugin import *

log = logging.getLogger('dump_config')

class OutputDumpConfig:
    """
        Dumps feed config in STDOUT in yaml at exit or abort event.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_exit(self, feed):
        import yaml
        print '--- config from feed: %s' % feed.name
        print yaml.safe_dump(feed.config)
        print '---'
        
    on_feed_abort = on_feed_exit

register_plugin(OutputDumpConfig, 'dump_config', debug=True)
