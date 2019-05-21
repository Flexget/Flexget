from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import argparse
import logging

from jinja2 import TemplateError, StrictUndefined, Undefined, UndefinedError
from jinja2.nativetypes import NativeEnvironment

from flexget import options, plugin
from flexget.event import event

log = logging.getLogger('cli_config')

"""
Allows specifying yaml configuration values from commandline parameters.

Variables in the config should be surrounded by {-- --}.

Configuration example::

  tasks:
    my task:
      rss: "{-- url --}"
      download: "{-- path --}"

Commandline example::

  flexget --cli-config url=http://some.url/ --cli-config path=~/downloads execute

"""


@event('manager.before_config_validate')
def substitute_cli_variables(config, manager):
    env_params = {
        'block_start_string': '^^disabled^^',
        'block_end_string': '^^disabled^^',
        'variable_start_string': '{--',
        'variable_end_string': '--}',
    }
    env = NativeEnvironment(**env_params)
    if manager.options.execute.cli_config:
        raise plugin.PluginError("--cli-config has been overhauled, check wiki for updated documentation.", logger=log)
    variables = dict(manager.options.cli_config)
    env.globals = variables
    for key in config:
        if key == 'tasks':
            # Hacky way to disable tasks/templates which don't have their cli-config variables defined
            env.undefined = StrictUndefined
            for task_name in config[key]:
                if task_name.startswith('_'):
                    continue
                try:
                    config[key][task_name] = _process(config[key][task_name], env)
                except UndefinedError as e:
                    log.warning('Disabling task `%s` because of undefined cli-config variable.', task_name)
                    config[key]['_'+task_name] = config[key].pop(task_name)
        else:
            # In other sections of the config, undefined variables will be blanked out
            env.undefined = Undefined
            config[key] = _process(config[key], env)
    return config


def key_value_pair(text):
    if '=' not in text:
        raise argparse.ArgumentTypeError('arguments must be in VARIABLE=VALUE form')
    return text.split('=', 1)


def _process(element, environment):
    if isinstance(element, dict):
        for k, v in element.items():
            new_key = _process(k, environment)
            if new_key:
                element[new_key] = element.pop(k)
                k = new_key
            val = _process(element[k], environment)
            if val:
                element[k] = val
    elif isinstance(element, list):
        for i, v in enumerate(element):
            val = _process(v, environment)
            if val:
                element[i] = val
    elif isinstance(element, str) and '{--' in element:
        try:
            template = environment.from_string(element)
            return template.render()
        except (TemplateError, TypeError, UndefinedError):
            log.warning('Error rendering cli-config variable: %s', element)
            return element
    return element


@event('options.register')
def register_parser_arguments():
    options.get_parser().add_argument(
        '--cli-config',
        action='append',
        type=key_value_pair,
        metavar='VARIABLE=VALUE',
        help='configuration parameters through commandline',
    )
    # This format is not actually allowed, it is here so we can show a better error message for old users
    options.get_parser('execute').add_argument(
        '--cli-config',
        nargs='+',
        type=key_value_pair,
        metavar='VARIABLE=VALUE',
        help=argparse.SUPPRESS,
    )
