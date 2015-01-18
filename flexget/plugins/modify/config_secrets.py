from __future__ import unicode_literals, division, absolute_import
import codecs
import os
import yaml

from jinja2 import TemplateError

from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.plugin import PluginError


@event('manager.before_config_validate')
def process_secrets(config, manager):
    if 'secrets' not in config:
        return
    secret_file = os.path.join(manager.config_base, config['secrets'])
    if not os.path.exists(secret_file):
        raise PluginError('File %s does not exist!' % secret_file)
    try:
        with codecs.open(secret_file, 'rb', 'utf-8') as f:
            raw_secrets = f.read()
        secrets = {'secrets': yaml.safe_load(raw_secrets) or {}}
    except yaml.YAMLError as e:
        raise PluginError('Invalid secrets file: %s' % e)
    _process(config, secrets)
    return config


def _process(element, secrets):
    # Environment isn't set up at import time, have to delay the import until here
    from flexget.utils.template import environment
    if isinstance(element, dict):
        for k, v in element.iteritems():
            new_key = _process(k, secrets)
            if new_key:
                element[new_key] = element.pop(k)
                k = new_key
            val = _process(element[k], secrets)
            if val:
                element[k] = val
    elif isinstance(element, list):
        for i, v in enumerate(element):
            val = _process(v, secrets)
            if val:
                element[i] = val
    elif isinstance(element, basestring) and '{{' in element:
        try:
            template = environment.from_string(element)
            return template.render(secrets)
        except (TemplateError, TypeError):
            return None


secrets_config_schema = {'type': 'string'}


@event('config.register')
def register_config():
    register_config_key('secrets', secrets_config_schema)
