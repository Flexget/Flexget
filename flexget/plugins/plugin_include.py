from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import priority, register_plugin, PluginError

log = logging.getLogger('include')


class PluginInclude(object):
    """
    Include configuration from another yaml file.

    Example::

      include: series.yml

    File content must be valid for a task configuration
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text') # TODO: file
        bundle = root.accept('list')
        bundle.accept('text')
        return root

    def get_config(self, task):
        config = task.config.get('include', None)
        #if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    @priority(254)
    def on_process_start(self, task):
        if not 'include' in task.config:
            return

        import yaml
        import os

        files = self.get_config(task)

        for name in files:
            name = os.path.expanduser(name)
            if not os.path.isabs(name):
                name = os.path.join(task.manager.config_base, name)
            include = yaml.load(file(name))
            log.debug('Merging %s into task %s' % (name, task.name))
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(include, task.config)
            except MergeException:
                raise PluginError('Failed to merge include file to task %s, incompatible datatypes' % (task.name))

register_plugin(PluginInclude, 'include', builtin=True)
