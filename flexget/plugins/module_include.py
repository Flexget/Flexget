import logging
from flexget.plugin import *

log = logging.getLogger('include')


class PluginInclude:
    """
    Include configuration from another yaml file.
    
    Example:
    
    include: series.yml
    
    File content must be valid for a feed configuration
    """

    def validator(self):
        from flexget import validator
        return validator.factory('text') # TODO: file
        
    def on_process_start(self, feed):
        if not 'include' in feed.config:
            return
    
        import yaml
        import os
    
        # just support one file now
        files = [feed.config['include']]
    
        for name in files:
            if not os.path.basename(name):
                name = os.path.join(feed.manager.config_base, name)
            name = os.path.expanduser(name)
            include = yaml.load(file(name))
            log.debug('Merging into feed %s' % (feed.name))
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(include, feed.config)
            except MergeException:
                raise PluginError('Failed to merge include file to feed %s, incompatible datatypes' % (feed.name))

register_plugin(PluginInclude, 'include', builtin=True, priorities=dict(process_start=254))
