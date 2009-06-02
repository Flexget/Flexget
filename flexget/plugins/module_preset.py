import logging
from flexget.manager import PluginWarning, PluginError

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

    def register(self, manager, parser):
        manager.register('preset', start_priority=255, builtin=True)
        
    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        root.accept('boolean')
        presets = root.accept('list')
        presets.accept('text')
        return root
        
    def process_start(self, feed):
        config = feed.config.get('preset', 'global')
        if isinstance(config, basestring):
            config = [config]
        # handles 'preset: no' form to turn off global preset on this feed
        elif isinstance(config, bool):
            if not config:
                config = []
            else:
                config = ['global']
                
        log.log(5, 'presets: %s' % config)
        
        for preset in config:
            log.debug('Merging preset %s into feed %s' % (preset, feed.name))
            if not preset in feed.manager.config:
                if preset=='global': continue
                raise PluginError('Unable to set preset %s for %s' % (preset, feed.name), log)
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(feed.manager.config[preset], feed.config)
            except MergeException:
                raise PluginError('Failed to merge preset %s to feed %s, incompatible datatypes' % (preset, feed.name))