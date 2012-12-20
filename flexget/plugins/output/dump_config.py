from __future__ import unicode_literals, division, absolute_import
import logging
from argparse import SUPPRESS
from flexget.plugin import register_plugin, register_parser_option, priority

log = logging.getLogger('dump_config')


class OutputDumpConfig(object):
    """
        Dumps task config in STDOUT in yaml at exit or abort event.
    """

    @priority(-255)
    def on_task_start(self, task):
        if task.manager.options.dump_config:
            import yaml
            print '--- config from task: %s' % task.name
            print yaml.safe_dump(task.config)
            print '---'
            task.abort(silent=True)
        if task.manager.options.dump_config_python:
            print task.config
            task.abort(silent=True)

register_plugin(OutputDumpConfig, 'dump_config', debug=True, builtin=True)
register_parser_option('--dump-config', action='store_true', dest='dump_config', default=False,
                       help='Display the config of each feed after preset merging/config generation occurs.')
register_parser_option('--dump-config-python', action='store_true', dest='dump_config_python', default=False,
                       help=SUPPRESS)
