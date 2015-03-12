from __future__ import unicode_literals, division, absolute_import
import logging
import os
import yaml

from flexget import plugin
from flexget.config_schema import one_or_more, process_config
from flexget.event import event
from flexget.utils.tools import MergeException, merge_dict_from_to

log = logging.getLogger('include')


class PluginInclude(object):
    """
    Include configuration from another yaml file.

    Example::

      include: series.yml

    File content must be valid for a task configuration
    """

    schema = one_or_more({'type': 'string'})

    @plugin.priority(256)
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
            errors = process_config(include, plugin.plugin_schemas(context='task'))
            if errors:
                log.error('Included file %s has invalid config:' % name)
                for error in errors:
                    log.error('[%s] %s', error.json_pointer, error.message)
                task.abort('Invalid config in included file %s' % name)
            log.debug('Merging %s into task %s' % (name, task.name))
            # merge
            try:
                merge_dict_from_to(include, task.config)
            except MergeException:
                raise plugin.PluginError('Failed to merge include file to task %s, incompatible datatypes' % task.name)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInclude, 'include', api_ver=2, builtin=True)
