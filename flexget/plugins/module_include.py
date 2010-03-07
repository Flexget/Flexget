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
        root = validator.factory()
        root.accept('text') # TODO: file
        bundle = root.accept('list')
        bundle.accept('text')
        return root

    def get_config(self, feed):
        config = feed.config.get('include', None)
        #if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    def on_process_start(self, feed):
        if not 'include' in feed.config:
            return

        import yaml
        import os

        files = self.get_config(feed)

        for name in files:
            name = os.path.expanduser(name)
            if not os.path.isabs(name):
                name = os.path.join(feed.manager.config_base, name)
            include = yaml.load(file(name))
            log.debug('Merging %s into feed %s' % (name, feed.name))
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(include, feed.config)
            except MergeException:
                raise PluginError('Failed to merge include file to feed %s, incompatible datatypes' % (feed.name))

register_plugin(PluginInclude, 'include', builtin=True, priorities=dict(process_start=254))
