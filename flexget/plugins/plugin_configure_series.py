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

                # Allow configure_series to set anything available to series
                if ('configure_series_path' in entry and isinstance(entry['configure_series_path'], basestring)):
                    s['path'] = entry['configure_series_path']
                if ('configure_series_set' in entry and isinstance(entry['configure_series_set'], dict)):
                    s['set'] = entry['configure_series_set']
                if ('configure_series_alternate_name' in entry
                    and isinstance(entry['configure_series_alternate_name'], (basestring, list))):
                    s['alternate_name'] = entry['configure_series_alternate_name']
                if ('configure_series_from_group' in entry
                    and isinstance(entry['configure_series_from_group'], (basestring, list))):
                    s['from_group'] = entry['configure_series_from_group']
                if ('configure_series_parse_only' in entry
                    and isinstance(entry['configure_series_parse_only'], bool)):
                    s['parse_only'] = entry['configure_series_parse_only']
                # Custom regexp options
                if ('configure_series_name_regexp' in entry
                    and isinstance(entry['configure_series_name_regexp'], (basestring, list))):
                    s['name_regexp'] = entry['configure_series_name_regexp']
                if ('configure_series_ep_regexp' in entry
                    and isinstance(entry['configure_series_ep_regexp'], (basestring, list))):
                    s['ep_regexp'] = entry['configure_series_ep_regexp']
                if ('configure_series_date_regexp' in entry
                    and isinstance(entry['configure_series_date_regexp'], (basestring, list))):
                    s['date_regexp'] = entry['configure_series_date_regexp']
                if ('configure_series_sequence_regexp' in entry
                    and isinstance(entry['configure_series_sequence_regexp'], (basestring, list))):
                    s['sequence_regexp'] = entry['configure_series_sequence_regexp']
                if ('configure_series_id_regexp' in entry
                    and isinstance(entry['configure_series_id_regexp'], (basestring, list))):
                    s['id_regexp'] = entry['configure_series_id_regexp']
                # Date parsing options
                if ('configure_series_date_yearfirst' in entry
                    and isinstance(entry['configure_series_date_yearfirst'], bool)):
                    s['date_yearfirst'] = entry['configure_series_date_yearfirst']
                if ('configure_series_date_dayfirst' in entry
                    and isinstance(entry['configure_series_date_dayfirst'], bool)):
                    s['date_dayfirst'] = entry['configure_series_date_dayfirst']
                # Quality options
                if ('configure_series_quality' in entry
                    and isinstance(entry['configure_series_quality'], basestring)):
                    s['quality'] = entry['configure_series_quality']
                if ('configure_series_qualities' in entry
                    and isinstance(entry['configure_series_qualities'], list)):
                    s['qualities'] = entry['configure_series_qualities']
                if ('configure_series_timeframe' in entry
                    and isinstance(entry['configure_series_timeframe'], basestring)):
                    s['timeframe'] = entry['configure_series_timeframe']
                if ('configure_series_upgrade' in entry
                    and isinstance(entry['configure_series_upgrade'], bool)):
                    s['upgrade'] = entry['configure_series_upgrade']
                if ('configure_series_target' in entry
                    and isinstance(entry['configure_series_target'], basestring)):
                    s['target'] = entry['configure_series_target']
                # Specials
                if ('configure_series_specials' in entry
                    and isinstance(entry['configure_series_specials'], bool)):
                    s['specials'] = entry['configure_series_specials']
                # Propers (can be boolean, or an interval string)
                if ('configure_series_propers' in entry
                    and isinstance(entry['configure_series_propers'], basestring)):
                    s['propers'] = entry['configure_series_propers']
                # Strict naming
                if ('configure_series_exact' in entry
                    and isinstance(entry['configure_series_exact'], bool)):
                    s['exact'] = entry['configure_series_exact']
                # Identified by)):
                if ('configure_series_identified_by' in entry
                    and isinstance(entry['configure_series_identified_by'], basestring)):
                    s['identified_by'] = entry['configure_series_identified_by']
                # Begin takes an ep, sequence or date identifier
                if ('configure_series_begin' in entry
                    and isinstance(entry['configure_series_begin'], basestring)):
                    s['begin'] = entry['configure_series_begin']

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
    plugin.register(ConfigureSeries, 'configure_series', api_ver=2)
