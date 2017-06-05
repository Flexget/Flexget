from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.template import render_from_entry, render_from_task, RenderError

log = logging.getLogger('log')


class PluginLog(object):
    """
    Log entries

    Simple example, log for entries that reach output::

      log: 'found {{title}} at {{url}}'

    Advanced Example::

      log:
        on_start:
          phase: "Started"
        on_input:
          for_entries: 'got {{title}}'
        on_output:
          for_accepted: 'accepted {{title}} - {{url}}'

    You can use all (available) entry fields in the command.
    """

    NAME = 'log'
    HANDLED_PHASES = ['start', 'input', 'filter', 'output', 'exit']

    schema = {
        'oneOf': [
            one_or_more({'type': 'string'}),
            {
                'type': 'object',
                'properties': {
                    'on_start': {'$ref': '#/definitions/phaseSettings'},
                    'on_input': {'$ref': '#/definitions/phaseSettings'},
                    'on_filter': {'$ref': '#/definitions/phaseSettings'},
                    'on_output': {'$ref': '#/definitions/phaseSettings'},
                    'on_exit': {'$ref': '#/definitions/phaseSettings'},
                    'logger_name': {'type': 'string', 'default': 'log'},
                },
                'additionalProperties': False
            }
        ],
        'definitions': {
            'phaseSettings': {
                'type': 'object',
                'properties': {
                    'level': {'enum': ['debug', 'error', 'info', 'trace',
                                       'verbose', 'warning'],
                              'default': 'info'},
                    'phase': one_or_more({'type': 'string'}),
                    'for_entries': one_or_more({'type': 'string'}),
                    'for_accepted': one_or_more({'type': 'string'}),
                    'for_rejected': one_or_more({'type': 'string'}),
                    'for_failed': one_or_more({'type': 'string'})
                },
                'additionalProperties': False
            }
        }
    }

    def prepare_config(self, config):
        if isinstance(config, basestring):
            config = {'on_output': {'level': 'info', 'for_accepted': config}}
        config['logger_name'] = config.get('logger_name', 'log')
        for phase_name in config:
            if phase_name.startswith('on_'):
                for items_name in config[phase_name]:
                    if items_name == "level":
                        continue
                    if isinstance(config[phase_name][items_name], basestring):
                        config[phase_name][items_name] = [config[phase_name][items_name]]
        return config

    def execute(self, task, phase_name, config):
        config = self.prepare_config(config)
        plugin_log = logging.getLogger(config['logger_name'])
        if phase_name not in config:
            log.debug('phase %s not configured' % phase_name)
            return

        name_map = {'for_entries': task.entries, 'for_accepted': task.accepted,
                    'for_rejected': task.rejected, 'for_failed': task.failed}

        for operation, entries in name_map.iteritems():
            if operation not in config[phase_name]:
                continue

            for entry in entries:
                for txt in config[phase_name][operation]:
                    # Do string replacement from entry
                    try:
                        txt = render_from_entry(txt, entry)
                    except RenderError as e:
                        log.error('Could not set log command for %s: %s'
                                % (entry['title'], e))
                        continue

                    if config[phase_name]['level'] == 'trace':
                        plugin_log.trace(txt)
                    elif config[phase_name]['level'] == 'debug':
                        plugin_log.debug(txt)
                    elif config[phase_name]['level'] == 'verbose':
                        plugin_log.verbose(txt)
                    elif config[phase_name]['level'] == 'info':
                        plugin_log.info(txt)
                    elif config[phase_name]['level'] == 'warning':
                        plugin_log.warning(txt)
                    elif config[phase_name]['level'] == 'error':
                        plugin_log.error(txt)

        # phase keyword in this
        if 'phase' in config[phase_name]:
            for txt in config[phase_name]['phase']:
                try:
                    txt = render_from_task(txt, task)
                except RenderError as e:
                    log.error('Error rendering `%s`: %s' % (txt, e))
                else:
                    if config[phase_name]['level'] == 'trace':
                        plugin_log.trace(txt)
                    elif config[phase_name]['level'] == 'debug':
                        plugin_log.debug(txt)
                    elif config[phase_name]['level'] == 'verbose':
                        plugin_log.verbose(txt)
                    elif config[phase_name]['level'] == 'info':
                        plugin_log.info(txt)
                    elif config[phase_name]['level'] == 'warning':
                        plugin_log.warning(txt)
                    elif config[phase_name]['level'] == 'error':
                        plugin_log.error(txt)

    def __getattr__(self, item):
        """Creates methods to handle task phases."""
        for phase in self.HANDLED_PHASES:
            if item == plugin.phase_methods[phase]:
                # A phase method we handle has been requested
                break
        else:
            # We don't handle this phase
            raise AttributeError(item)

        def phase_handler(task, config):
            self.execute(task, 'on_' + phase, config)

        # Make sure we run after other plugins so exec can use their output
        phase_handler.priority = 100
        return phase_handler


@event('plugin.register')
def register_plugin():
    plugin.register(PluginLog, 'log', api_ver=2)
