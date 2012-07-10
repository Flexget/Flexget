import logging
from argparse import SUPPRESS
from flexget.plugin import register_plugin, register_parser_option

log = logging.getLogger('dump_config')


class OutputDumpConfig(object):
    """
        Dumps feed config in STDOUT in yaml at exit or abort event.
    """

    def on_feed_exit(self, feed):
        if feed.manager.options.dump_config:
            import yaml
            print '--- config from feed: %s' % feed.name
            print yaml.safe_dump(feed.config)
            print '---'
        if feed.manager.options.dump_config_python:
            print feed.config

    on_feed_abort = on_feed_exit

register_plugin(OutputDumpConfig, 'dump_config', debug=True, builtin=True)
register_parser_option('--dump-config', action='store_true', dest='dump_config', default=False, \
                       help=SUPPRESS)
register_parser_option('--dump-config-python', action='store_true', dest='dump_config_python', default=False, \
                       help=SUPPRESS)
