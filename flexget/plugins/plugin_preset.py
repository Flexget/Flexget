from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import validator
from flexget.manager import register_config_key
from flexget.plugin import priority, register_plugin, PluginError, register_parser_option
from flexget.utils.tools import MergeException, merge_dict_from_to

log = logging.getLogger('preset')


class PluginPreset(object):
    """
    Use presets.

    Example::

      preset: movies

    Example, list of presets::

      preset:
        - movies
        - imdb
    """

    schema = {
        'oneOf': [
            {'title': 'list of presets','type': 'array', 'items': {'type': 'string'}},
            {'title': 'single preset', 'type': 'string'},
            {'title': 'disable presets', 'type': 'boolean', 'enum': [False]}
        ]
    }

    def __init__(self):
        self.warned = False

    def prepare_config(self, config):
        if config is None or isinstance(config, bool):
            config = []
        elif isinstance(config, basestring):
            config = [config]
        return config

    @priority(255)
    def on_process_start(self, task, config):
        if config is False: # handles 'preset: no' form to turn off preset on this task
            return
        config = self.prepare_config(config)

        # add global in except when disabled with no_global
        if 'no_global' in config:
            config.remove('no_global')
            if 'global' in config:
                config.remove('global')
        elif not 'global' in config:
            config.append('global')

        toplevel_presets = task.manager.config.get('presets', {})

        # apply presets
        for preset in config:
            if preset not in toplevel_presets:
                if preset == 'global':
                    continue
                raise PluginError('Unable to find preset %s for task %s' % (preset, task.name), log)
            if toplevel_presets[preset] is None:
                log.warning('Preset `%s` is empty. Nothing to merge.' % preset)
                continue
            log.debug('Merging preset %s into task %s' % (preset, task.name))

            # We make a copy here because we need to remove
            preset_config = toplevel_presets[preset]
            # When there are presets within presets we remove the preset
            # key from the config and append it's items to our own
            if 'preset' in preset_config:
                nested_presets = self.prepare_config(preset_config['preset'])
                for nested_preset in nested_presets:
                    if nested_preset not in config:
                        config.append(nested_preset)
                    else:
                        log.warning('Presets contain each other in a loop.')
                # Replace preset_config with a copy without the preset key, to avoid merging errors
                preset_config = dict(preset_config)
                del preset_config['preset']

            # Merge
            try:
                merge_dict_from_to(preset_config, task.config)
            except MergeException as exc:
                raise PluginError('Failed to merge preset %s to task %s. Error: %s' %
                                  (preset, task.name, exc.value))

        log.trace('presets: %s' % config)

        # implements --preset NAME
        if task.manager.options.preset:
            if task.manager.options.preset not in config:
                task.enabled = False
                return


class DisablePlugin(object):
    """
    Allows disabling plugins when using presets.

    Example::

      presets:
        movies:
          download: ~/torrents/movies/
          .
          .

      tasks:
        nzbs:
          preset: movies
          disable_plugin:
            - download
          sabnzbd:
            .
            .

      # Task nzbs uses all other configuration from preset movies but removes the download plugin
    """

    def validator(self):
        root = validator.factory()
        root.accept('text')
        presets = root.accept('list')
        presets.accept('text')
        return root

    @priority(250)
    def on_task_start(self, task, config):
        if isinstance(config, basestring):
            config = [config]
        # let's disable them
        for disable in config:
            if disable in task.config:
                log.debug('disabling %s' % disable)
                del(task.config[disable])


root_config_schema = {
    'type': 'object',
    'additionalProperties': {}
}


register_config_key('presets', root_config_schema)
register_plugin(PluginPreset, 'preset', builtin=True, api_ver=2)
register_plugin(DisablePlugin, 'disable_plugin', api_ver=2)

register_parser_option('--preset', action='store', dest='preset', default=False,
                       metavar='NAME', help='Execute tasks with given preset.')
