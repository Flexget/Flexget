from flexget.plugin import register_plugin, get_plugin_by_name, get_plugins_by_phase, PluginError
from flexget.plugins.filter.series import FilterSeriesBase
import logging

log = logging.getLogger('import_series')


class ImportSeries(FilterSeriesBase):

    """Generates series configuration from any input (supporting API version 2, soon all)

    Configuration::

      import_series:
        [settings]:
           # same configuration as series plugin
        from:
          [input plugin]: <configuration>

    Example::

      import_series:
        settings:
          quality: 720p
        from:
          listdir:
            - /media/series
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        self.build_options_validator(root.accept('dict', key='settings'))
        from_section = root.accept('dict', key='from', required=True)
        # Build a dict validator that accepts the available input plugins and their settings
        for plugin in get_plugins_by_phase('input'):
            if plugin.api_ver > 1 and hasattr(plugin.instance, 'validator'):
                from_section.accept(plugin.instance.validator, key=plugin.name)
        return root

    def on_feed_start(self, feed, config):

        series = set()
        for input_name, input_config in config.get('from', {}).iteritems():
            input = get_plugin_by_name(input_name)
            if input.api_ver == 1:
                raise PluginError('Plugin %s does not support API v2' % input_name)

            method = input.phase_handlers['input']
            result = method(feed, input_config)
            if not result:
                log.warning('Input %s did not return anything' % input_name)
                continue

            series.update([x['title'] for x in result])

        if not series:
            log.info('Did not get any series to generate series configuration')
            return

        # Make a series config with the found series
        series_config = {'generated_series': list(series)}
        # If options were specified, add them to the series config
        if 'settings' in config:
            series_config['settings'] = {'generated_series': config['settings']}
        # Merge our series config in with the base series config
        self.merge_config(feed, series_config)


register_plugin(ImportSeries, 'import_series', api_ver=2)
