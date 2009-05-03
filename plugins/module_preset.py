import logging
from manager import PluginWarning, MergeException

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
        import validator
        root = validator.factory()
        root.accept('text')
        presets = root.accept('list')
        presets.accept('text')
        return root
        
    def process_start(self, feed):
        config = feed.config.get('preset', 'global')
        if isinstance(config, basestring):
            config = [config]
        log.log(5, 'presets: %s' % config)
        
        for preset in config:
            log.debug('Merging preset %s into feed %s' % (preset, feed.name))
            if not preset in feed.manager.config:
                if preset=='global': continue
                raise PluginWarning('Unable to set preset %s for %s' % (preset, feed.name))
            # merge
            from utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(feed.manager.config[preset], feed.config)
            except MergeException:
                raise PluginWarning('Failed to merge preset %s to feed %s, incompatible datatypes' % (preset, feed.name))