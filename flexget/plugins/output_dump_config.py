import logging
from optparse import SUPPRESS_HELP
from flexget.plugin import register_plugin, register_parser_option

log = logging.getLogger('dump_config')


class OutputDumpConfig(object):
    """
        Dumps feed config in STDOUT in yaml at exit or abort event.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_end(self, feed):
        if feed.manager.options.dump_config:
            import yaml
            print '--- config from feed: %s' % feed.name
            print yaml.safe_dump(feed.config)
            print '---'
        if feed.manager.options.dump_config_python:
            print feed.config

register_plugin(OutputDumpConfig, 'dump_config', debug=True, builtin=True)
register_parser_option('--dump-config', action='store_true', dest='dump_config', default=False, \
                       help=SUPPRESS_HELP)
register_parser_option('--dump-config-python', action='store_true', dest='dump_config_python', default=False, \
                       help=SUPPRESS_HELP)
