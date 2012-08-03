import logging
from argparse import SUPPRESS
from flexget.plugin import register_plugin, register_parser_option

log = logging.getLogger('dump_config')


class OutputDumpConfig(object):
    """
        Dumps task config in STDOUT in yaml at exit or abort event.
    """

    def on_task_exit(self, task):
        if task.manager.options.dump_config:
            import yaml
            print '--- config from task: %s' % task.name
            print yaml.safe_dump(task.config)
            print '---'
        if task.manager.options.dump_config_python:
            print task.config

    on_task_abort = on_task_exit

register_plugin(OutputDumpConfig, 'dump_config', debug=True, builtin=True)
register_parser_option('--dump-config', action='store_true', dest='dump_config', default=False, \
                       help=SUPPRESS)
register_parser_option('--dump-config-python', action='store_true', dest='dump_config_python', default=False, \
                       help=SUPPRESS)
