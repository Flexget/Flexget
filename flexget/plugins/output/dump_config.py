from argparse import SUPPRESS

from loguru import logger

from flexget import options, plugin
from flexget.event import event
from flexget.terminal import console

logger = logger.bind(name='dump_config')


class OutputDumpConfig:
    """
        Dumps task config in STDOUT in yaml at exit or abort event.
    """

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_start(self, task, config):
        if task.options.dump_config:
            import yaml

            console('--- config from task: %s' % task.name)
            console(yaml.safe_dump(task.config))
            console('---')
            task.abort(silent=True)
        if task.options.dump_config_python:
            console(task.config)
            task.abort(silent=True)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputDumpConfig, 'dump_config', debug=True, builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    exec_parser.add_argument(
        '--dump-config',
        action='store_true',
        dest='dump_config',
        default=False,
        help='display the config of each feed after template merging/config generation occurs',
    )
    exec_parser.add_argument(
        '--dump-config-python',
        action='store_true',
        dest='dump_config_python',
        default=False,
        help=SUPPRESS,
    )
