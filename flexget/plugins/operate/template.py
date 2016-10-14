from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

from sqlalchemy import Column, Integer, String, Unicode

from flexget import options, plugin, db_schema
from flexget.event import event
from flexget.config_schema import register_config_key
from flexget.manager import Session
from flexget.utils.tools import MergeException, merge_dict_from_to

log = logging.getLogger('template')
Base = db_schema.versioned_base('template_hash', 0)


class TemplateConfigHash(Base):
    """Stores the config hash for tasks so that we can tell if the config has changed since last run."""

    __tablename__ = 'template_config_hash'

    id = Column(Integer, primary_key=True)
    task = Column('name', Unicode, index=True, nullable=False)
    hash = Column('hash', String)

    def __repr__(self):
        return '<TemplateConfigHash(task=%s,hash=%s)>' % (self.task, self.hash)


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
                'items': {'$ref': '#/definitions/template'}},
            {
                'description': 'Apply a single template to this task.',
                'allOf': [{'$ref': '#/definitions/template'}]
            },
            {
                'description': 'Disable all templates on this task.',
                'type': 'boolean',
                'enum': [False]
            }
        ],
        'definitions': {
            'template': {
                'type': 'string',
                'description': 'Name of a template which will be applied to this task.',
                'links': [{'rel': 'settings', 'href': '/api/config/templates/{$}'}]
            }
        }
    }

    def prepare_config(self, config):
        if config is None or isinstance(config, bool):
            config = []
        elif isinstance(config, basestring):
            config = [config]
        return config

    @plugin.priority(257)
    def on_task_start(self, task, config):
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
                raise plugin.PluginError('Unable to find template %s for task %s' % (template, task.name), log)
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
                merge_dict_from_to(template_config, task.config)
            except MergeException as exc:
                raise plugin.PluginError('Failed to merge template %s to task %s. Error: %s' %
                                         (template, task.name, exc.value))

        # TODO: Better handling of config_modified flag for templates???
        with Session() as session:
            last_hash = session.query(TemplateConfigHash).filter(TemplateConfigHash.task == task.name).first()
            task.config_modified, config_hash = task.is_config_modified(last_hash)
            if task.config_modified:
                session.add(TemplateConfigHash(task=task.name, hash=config_hash))

        log.trace('templates: %s' % config)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTemplate, 'template', builtin=True, api_ver=2)


@event('config.register')
def register_config():
    root_config_schema = {
        'type': 'object',
        'additionalProperties': plugin.plugin_schemas(context='task')
    }
    register_config_key('templates', root_config_schema)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('-T', '--template', metavar='NAME',
                                               help='execute tasks using given template')
