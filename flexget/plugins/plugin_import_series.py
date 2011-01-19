from flexget.plugin import register_plugin, get_plugin_by_name, PluginError
from flexget.plugins.filter_series import FilterSeriesBase
import logging

log = logging.getLogger('imp_series')


class ImportSeries(FilterSeriesBase):

    """Generates series configuration from any input (supporting API version 2, soon all)

    Configuration:

    import_series:
      [settings]:
         # same configuration as series plugin
      from:
        [input plugin]: <configuration>

    Example:

    import_series:
      settings:
        quality: 720p
      from:
        listdir:
          - /media/series
    """

    def on_feed_start(self, feed, config):

        series = set()
        for input_name, input_config in config.get('from', {}).iteritems():
            input = get_plugin_by_name(input_name)
            if input.api_ver == 1:
                raise PluginError('Plugin %s does not support API v2' % input_name)

            method = input.event_handlers['on_feed_input']
            result = method(feed, input_config)
            if not result:
                log.warning('Input %s did not return anything' % input_name)

            series_names = [x['title'] for x in result]
            series = set.union(series, set(series_names))

        if not series:
            log.info('Did not get any series to generate series configuration')
            return

        series_config = {}
        if 'settings' in config:
            series_config.setdefault('settings', {})
            series_config['settings'].setdefault('generated_series', config['settings'])
        series_config.setdefault('generated_series', list(series))

        self.merge_config(feed, series_config)


register_plugin(ImportSeries, 'import_series', api_ver=2)
