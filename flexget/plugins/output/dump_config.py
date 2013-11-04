from __future__ import unicode_literals, division, absolute_import
import logging

from argparse import SUPPRESS

from flexget import options, plugin
from flexget.event import event

log = logging.getLogger('dump_config')


class OutputDumpConfig(object):
    """
        Dumps task config in STDOUT in yaml at exit or abort event.
    """

    @plugin.priority(-255)
    def on_task_start(self, task, config):
        if task.options.dump_config:
            import yaml
            print '--- config from task: %s' % task.name
            print yaml.safe_dump(task.config)
            print '---'
            task.abort(silent=True)
        if task.options.dump_config_python:
            print task.config
            task.abort(silent=True)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputDumpConfig, 'dump_config', debug=True, builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    exec_parser.add_argument('--dump-config', action='store_true', dest='dump_config', default=False,
                             help='display the config of each feed after template merging/config generation occurs')
    exec_parser.add_argument('--dump-config-python', action='store_true', dest='dump_config_python', default=False,
                             help=SUPPRESS)
