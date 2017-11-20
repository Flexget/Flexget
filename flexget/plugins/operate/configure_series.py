from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from sqlalchemy import Column, Integer, Unicode

from flexget import db_schema, plugin
from flexget.config_schema import process_config
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.plugins.filter.series import FilterSeriesBase
from flexget.utils.tools import get_config_hash

log = logging.getLogger('configure_series')


class ConfigureSeries(FilterSeriesBase):
    """Generates series configuration from any input (supporting API version 2, soon all)

    Configuration::

      configure_series:
        [settings]:
           # same configuration as series plugin
        from:
          [input plugin]: <configuration>

    Example::

      configure_series:
        settings:
          quality: 720p
        from:
          listdir:
            - /media/series
    """

    @property
    def schema(self):
        return {
            'type': 'object',
            'properties': {
                'settings': self.settings_schema,
                'from': {'$ref': '/schema/plugins?phase=input'}
            },
            'required': ['from'],
            'additionalProperties': False
        }

    def on_task_prepare(self, task, config):

        series = {}
        for input_name, input_config in config.get('from', {}).items():
            input = plugin.get_plugin_by_name(input_name)
            if input.api_ver == 1:
                raise plugin.PluginError('Plugin %s does not support API v2' % input_name)

            method = input.phase_handlers['input']
            try:
                result = method(task, input_config)
            except PluginError as e:
                log.warning('Error during input plugin %s: %s' % (input_name, e))
                continue
            if not result:
                log.warning('Input %s did not return anything' % input_name)
                continue

            for entry in result:
                s = series.setdefault(entry['title'], {})
                if entry.get('tvdb_id'):
                    s['set'] = {'tvdb_id': entry['tvdb_id']}

                # Allow configure_series to set anything available to series
                for key, schema in self.settings_schema['properties'].items():
                    if 'configure_series_' + key in entry:
                        errors = process_config(entry['configure_series_' + key], schema, set_defaults=False)
                        if errors:
                            log.debug('not setting series option %s for %s. errors: %s' % (key, entry['title'], errors))
                        else:
                            s[key] = entry['configure_series_' + key]

        if not series:
            log.info('Did not get any series to generate series configuration')
            return

        # Make a series config with the found series
        # Turn our dict of series with settings into a list of one item dicts
        series_config = {'generated_series': [dict([x]) for x in series.items()]}
        # If options were specified, add them to the series config
        if 'settings' in config:
            series_config['settings'] = {'generated_series': config['settings']}
        # Merge our series config in with the base series config
        self.merge_config(task, series_config)


@event('plugin.register')
def register_plugin():
    plugin.register(ConfigureSeries, 'configure_series', api_ver=2)
