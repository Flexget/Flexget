from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import options, plugin
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.utils.tools import MergeException

plugin_name = 'template'
log = logging.getLogger(plugin_name)


class PluginTemplate(object):
    """
    Appyly templates with preconfigured plugins to a task config.

    Example::

      template: movies

    Example, list of templates::

      template:
        - movies
        - imdb
    """

    schema = {
        'oneOf': [
            {
                'description': 'Apply multiple templates to this task.',
                'type': 'array',
                'items': {'$ref': '#/definitions/template'},
            },
            {
                'description': 'Apply a single template to this task.',
                'allOf': [{'$ref': '#/definitions/template'}],
            },
            {
                'description': 'Disable all templates on this task.',
                'type': 'boolean',
                'enum': [False],
            },
        ],
        'definitions': {
            'template': {
                'type': 'string',
                'description': 'Name of a template which will be applied to this task.',
                'links': [{'rel': 'settings', 'href': '/api/config/templates/{$}'}],
            }
        },
    }

    def prepare_config(self, config):
        if config is None or isinstance(config, bool):
            config = []
        elif isinstance(config, str):
            config = [config]
        return config

    @plugin.priority(257)
    def on_task_prepare(self, task, config):
        if config is False:  # handles 'template: no' form to turn off template on this task
            return
        # implements --template NAME
        if task.options.template:
            if not config or task.options.template not in config:
                task.abort('does not use `%s` template' % task.options.template, silent=True)

        config = self.prepare_config(config)

        # add global in except when disabled with no_global
        if 'no_global' in config:
            config.remove('no_global')
            if 'global' in config:
                config.remove('global')
        elif 'global' not in config:
            config.append('global')

        toplevel_templates = task.manager.config.get('templates', {})

        # apply templates
        for template in config:
            if template not in toplevel_templates:
                if template == 'global':
                    continue
                raise plugin.PluginError(
                    'Unable to find template %s for task %s' % (template, task.name), log
                )
            if toplevel_templates[template] is None:
                log.warning('Template `%s` is empty. Nothing to merge.' % template)
                continue
            log.debug('Merging template %s into task %s' % (template, task.name))

            # We make a copy here because we need to remove
            template_config = toplevel_templates[template]
            # When there are templates within templates we remove the template
            # key from the config and append it's items to our own
            if 'template' in template_config:
                nested_templates = self.prepare_config(template_config['template'])
                for nested_template in nested_templates:
                    if nested_template not in config:
                        config.append(nested_template)
                    else:
                        log.warning('Templates contain each other in a loop.')
                # Replace template_config with a copy without the template key, to avoid merging errors
                template_config = dict(template_config)
                del template_config['template']

            # Merge
            try:
                task.merge_config(template_config)
            except MergeException as exc:
                raise plugin.PluginError(
                    'Failed to merge template %s to task %s. Error: %s'
                    % (template, task.name, exc.value)
                )

        log.trace('templates: %s', config)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTemplate, 'template', builtin=True, api_ver=2)


@event('config.register')
def register_config():
    root_config_schema = {
        'type': 'object',
        'additionalProperties': plugin.plugin_schemas(interface='task'),
    }
    register_config_key('templates', root_config_schema)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '-T', '--template', metavar='NAME', help='execute tasks using given template'
    )
