from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from sqlalchemy import Column, Integer, Unicode

from flexget import db_schema, plugin
from flexget.event import event
from flexget.plugins.filter.series import FilterSeriesBase

log = logging.getLogger('configure_series')
Base = db_schema.versioned_base('import_series', 0)


class LastHash(Base):
    __tablename__ = 'import_series_last_hash'

    id = Column(Integer, primary_key=True)
    task = Column(Unicode)
    hash = Column(Unicode)


class ImportSeries(FilterSeriesBase):

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
            'additionalProperties': False
        }

    def on_task_start(self, task, config):

        series = {}
        for input_name, input_config in config.get('from', {}).iteritems():
            input = plugin.get_plugin_by_name(input_name)
            if input.api_ver == 1:
                raise plugin.PluginError('Plugin %s does not support API v2' % input_name)

            method = input.phase_handlers['input']
            result = method(task, input_config)
            if not result:
                log.warning('Input %s did not return anything' % input_name)
                continue

            for entry in result:
                s = series.setdefault(entry['title'], {})
                if entry.get('tvdb_id'):
                    s['set'] = {'tvdb_id': entry['tvdb_id']}

        # Set the config_modified flag if the list of shows changed since last time
        new_hash = hashlib.md5(unicode(sorted(series))).hexdigest().decode('ascii')
        last_hash = task.session.query(LastHash).filter(LastHash.task == task.name).first()
        if not last_hash:
            last_hash = LastHash(task=task.name)
            task.session.add(last_hash)
        if last_hash.hash != new_hash:
            task.config_changed()
        last_hash.hash = new_hash

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


@event('plugin.register')
def register_plugin():
    plugin.register(ImportSeries, 'configure_series', api_ver=2)
