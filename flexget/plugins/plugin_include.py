from __future__ import unicode_literals, division, absolute_import
import logging
import os
import yaml

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

log = logging.getLogger('include')


class PluginInclude(object):
    """
    Include configuration from another yaml file.

    Example::

      include: series.yml

    File content must be valid for a task configuration
    """

    schema = one_or_more({'type': 'string'})

    # TODO: 1.2 I think this needs to run on manager.pre-process event, so that config from other file gets validated
    @plugin.priority(254)
    def on_task_start(self, task, config):
        if not config:
            return

        files = config
        if isinstance(config, basestring):
            files = [config]

        for name in files:
            name = os.path.expanduser(name)
            if not os.path.isabs(name):
                name = os.path.join(task.manager.config_base, name)
            include = yaml.load(file(name))
            if not isinstance(include, dict):
                raise plugin.PluginError('Include file format is invalid: %s' % name)
            log.debug('Merging %s into task %s' % (name, task.name))
            # merge
            from flexget.utils.tools import MergeException, merge_dict_from_to
            try:
                merge_dict_from_to(include, task.config)
            except MergeException:
                raise plugin.PluginError('Failed to merge include file to task %s, incompatible datatypes' % task.name)

@event('plugin.register')
def register_plugin():
    plugin.register(PluginInclude, 'include', api_ver=2, builtin=True)
