from loguru import logger

from flexget import plugin
from flexget.config_schema import process_config
from flexget.event import event
from flexget.plugin import PluginError

from . import series as plugin_series

logger = logger.bind(name='configure_series')


class ConfigureSeries(plugin_series.FilterSeriesBase):
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
                'from': {'$ref': '/schema/plugins?phase=input'},
            },
            'required': ['from'],
            'additionalProperties': False,
        }

    def on_task_prepare(self, task, config):

        series = {}
        for input_name, input_config in config.get('from', {}).items():
            input_plugin = plugin.get_plugin_by_name(input_name)
            method = input_plugin.phase_handlers['input']
            try:
                result = method(task, input_config)
            except PluginError as e:
                logger.warning('Error during input plugin {}: {}', input_name, e)
                continue
            if not result:
                logger.warning('Input {} did not return anything', input_name)
                continue

            for entry in result:
                s = series.setdefault(entry['title'], {})
                if entry.get('tvdb_id'):
                    s['set'] = {'tvdb_id': entry['tvdb_id']}

                # Allow configure_series to set anything available to series
                for key, schema in self.settings_schema['properties'].items():
                    if 'configure_series_' + key in entry:
                        errors = process_config(
                            entry['configure_series_' + key], schema, set_defaults=False
                        )
                        if errors:
                            logger.debug(
                                'not setting series option {} for {}. errors: {}',
                                key,
                                entry['title'],
                                errors,
                            )
                        else:
                            s[key] = entry['configure_series_' + key]

        if not series:
            logger.info('Did not get any series to generate series configuration')
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
