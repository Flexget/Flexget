from __future__ import unicode_literals, division, absolute_import
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

    def on_task_start(self, task, config):

        series = {}
        for input_name, input_config in config.get('from', {}).iteritems():
            input = get_plugin_by_name(input_name)
            if input.api_ver == 1:
                raise PluginError('Plugin %s does not support API v2' % input_name)

            method = input.phase_handlers['input']
            result = method(task, input_config)
            if not result:
                log.warning('Input %s did not return anything' % input_name)
                continue

            for entry in result:
                s = series.setdefault(entry['title'], {})
                if entry.get('tvdb_id'):
                    s['set'] = {'tvdb_id': entry['tvdb_id']}

        if not series:
            log.info('Did not get any series to generate series configuration')
            return

        # Make a series config with the found series
        # Turn our dict of series with settings into a list of one item dicts
        series_config = {'generated_series': [dict([s]) for s in series.iteritems()]}
        # If options were specified, add them to the series config
        if 'settings' in config:
            series_config['settings'] = {'generated_series': config['settings']}
        # Merge our series config in with the base series config
        self.merge_config(task, series_config)


register_plugin(ImportSeries, 'import_series', api_ver=2)
