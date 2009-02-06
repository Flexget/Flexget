import logging
import datetime
from manager import ModuleWarning, MergeException

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('preset')

class ModulePreset:

    """
        Use presets
    """

    def register(self, manager, parser):
        manager.register('preset', start_priority=255, builtin=True)
        
    def validate(self, config):
        if not isinstance(config, basestring) and not isinstance(config, list):
            return ['wrong datatype']
        
    def feed_start(self, feed):
        config = feed.config.get('preset', 'global')
        if isinstance(config, basestring):
            config = [config]
        log.debug('presets: %s' % config)
        
        for preset in config:
            log.debug('Merging preset %s into feed %s' % (preset, feed.name))
            if not feed.manager.config.has_key(preset):
                if preset=='global': continue
                raise ModuleWarning('Unable to set preset %s for %s' % (preset, feed.name))
            try:
                feed.manager.merge_dict_from_to(feed.manager.config[preset], feed.config)
            except MergeException, e:
                raise ModuleWarning('Failed to merge preset %s to feed %s, incompatible datatypes' % (preset, feed.name))

            # re-validate feed after changes in configuration
            errors = feed.validate()
            if errors:
                raise ModuleWarning('Preset caused configuration errors')
            
