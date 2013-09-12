from __future__ import unicode_literals, division, absolute_import
import logging
import os
import yaml

from flexget.plugin import priority, register_plugin, PluginError
from flexget.config_schema import one_or_more

log = logging.getLogger('include')


class PluginInclude(object):
    """
    Include configuration from another yaml file.

    Example::

      include: series.yml

    File content must be valid for a task configuration
    """

    schema = one_or_more({'type': 'string', 'format': 'file'})

    def get_config(self, task):
        config = task.config.get('include', None)
        #if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    @priority(254)
    def on_process_start(self, task, config):
        if not config:
            return

        if isinstance(config, basestring):
            files = [config]
        else:
            files = config

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

register_plugin(PluginInclude, 'include', api_ver=2, builtin=True)
