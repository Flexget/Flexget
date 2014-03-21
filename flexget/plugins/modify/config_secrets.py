from __future__ import unicode_literals, division, absolute_import
import codecs
import os
import yaml

from flexget.config_schema import register_config_key
from flexget.event import event
    
@event('manager.before_config_validate')
def process_secrets(manager):
    if not 'secrets' in manager.config:
        return
    secret_file = os.path.join(manager.config_base, manager.config['secrets'])
    if not os.path.exists(secret_file):
        raise Exception('File %s does not exists!' % secret_file)
    try:
        with codecs.open(secret_file, 'rb', 'utf-8') as f:
            raw_secrets = f.read()
        secrets = {'secrets': yaml.safe_load(raw_secrets) or {}}
    except Exception as e:
        raise Exception('Invalid secrets file: ' + str(e))
    _process(manager.config, secrets)

def _process(element, secrets):
    from flexget.utils.template import environment
    if isinstance(element, dict):
        for k in element:
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
        except:
            return None

secrets_config_schema = {
    'type': 'string'
}

@event('config.register')
def register_config():
    register_config_key('secrets', secrets_config_schema)