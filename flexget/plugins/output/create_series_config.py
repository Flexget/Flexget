from __future__ import unicode_literals, division, absolute_import
import logging
import yaml

from flexget import plugin
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('create_config')


class CreateSeriesConfig(object):
    """
    Create a yaml file with series configuration that can be include in the main 
    config. Each entry with a series_name field became a series setup.
    Field tvdb_id, if found, is included as well.
    Optional fields: series_id can became the begin option (first episode to 
    download); quality and specials can be used too.
    
    Example::
    
      create_series_config:
        set_fields:
          - begin
          - quality
        filename: 'C:\Whatever\MyTVShows.yml'
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'set_fields': {'type': 'array', 'items': {'enum': ['begin', 'quality', 'specials']}},
            'filename': {'type': 'string'}
        },
        'required': ['filename'],
        'additionalProperties': False
    }
    
    def on_task_output(self, task, config):
        chk = []
        outdata = {'series': []}
        for entry in task.accepted:
            if not entry.get('series_name') or entry['series_name'] in chk:
                continue
            # root
            sroot = {}
            if 'begin' in config.get('set_fields', []) and entry.get('series_id'):
                sroot['begin'] = entry['series_id']
            if 'quality' in config.get('set_fields', []) and entry.get('quality'):
                sroot['quality'] = entry['quality']
            if 'specials' in config.get('set_fields', []) and 'specials' in entry: 
                sroot['specials'] = entry['specials']
            # "set" node
            sset = {}
            if entry.get('tvdb_id'):
                sset['tvdb_id'] = int(entry['tvdb_id'])
            if sset:
                sroot['set'] = sset
            # done
            if sroot:
                outdata['series'].append({entry['series_name']: sroot})
            else:
                outdata['series'].append(entry['series_name'])
            chk.append(entry['series_name'])
        if chk:
            with open(config['filename'], 'w') as outfile:
                outfile.write(yaml.dump(outdata, default_flow_style=False))
            log.info('Wrote settings for %d series in %s' % (len(chk), config['filename']))


@event('plugin.register')
def register_plugin():
    plugin.register(CreateSeriesConfig, 'create_series_config', api_ver=2)
