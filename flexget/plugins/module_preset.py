import logging
from flexget.plugin import *

log = logging.getLogger('preset')

class PluginPreset:
    """
        Use presets.
        
        Example:
        
        preset: movies
        
        Example 2:
        
        preset:
          - movies
          - imdb
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        root.accept('boolean')
        presets = root.accept('list')
        presets.accept('text')
        return root
        
    def on_process_start(self, feed):
        config = feed.config.get('preset', 'global')
        if isinstance(config, basestring):
            config = [config]
        elif isinstance(config, bool): # handles 'preset: no' form to turn off preset on this feed
            if not config:
                return

        # implements --preset NAME
        if feed.manager.options.preset:
            if feed.manager.options.preset not in config:
                feed.enabled = False
                return
        
        # add global in except when disabled with no_global
        if 'no_global' in config:
            config.remove('no_global')
            if 'global' in config:
                config.remove('global')
        elif not 'global' in config:
            config.append('global')
                
        log.log(5, 'presets: %s' % config)
        
        for preset in config:
            if preset != 'global':
                log.debug('Merging preset %s into feed %s' % (preset, feed.name))
            if not preset in feed.manager.config:
                if preset == 'global': 
                    continue
                raise PluginError('Unable to set preset %s for %s' % (preset, feed.name), log)
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(feed.manager.config[preset], feed.config)
            except MergeException:
                raise PluginError('Failed to merge preset %s to feed %s, incompatible datatypes' % (preset, feed.name))

register_plugin(PluginPreset, 'preset', builtin=True, priorities={'start': 255})


register_parser_option('--preset', action='store', dest='preset', default=False,
                       metavar='NAME', help='Execute feeds with given preset.')

