from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import io
import logging
import os

import yaml

from flexget import plugin
from flexget.config_schema import one_or_more, process_config
from flexget.event import event
from flexget.utils.tools import MergeException

plugin_name = 'include'
log = logging.getLogger(plugin_name)


class PluginInclude(object):
    """
    Include configuration from another yaml file.

    Example::

      include: series.yml

    File content must be valid for a task configuration
    """

    schema = one_or_more({'type': 'string'})

    @plugin.priority(256)
    def on_task_prepare(self, task, config):
        if not config:
            return

        files = config
        if isinstance(config, str):
            files = [config]

        for file_name in files:
            file = os.path.expanduser(file_name)
            if not os.path.isabs(file):
                file = os.path.join(task.manager.config_base, file)
            with io.open(file, encoding='utf-8') as inc_file:
                include = yaml.safe_load(inc_file)
                inc_file.flush()
            errors = process_config(include, plugin.plugin_schemas(interface='task'))
            if errors:
                log.error('Included file %s has invalid config:', file)
                for error in errors:
                    log.error('[%s] %s', error.json_pointer, error.message)
                task.abort('Invalid config in included file %s' % file)

            log.debug('Merging %s into task %s', file, task.name)
            # merge
            try:
                task.merge_config(include)
            except MergeException:
                raise plugin.PluginError(
                    'Failed to merge include file to task %s, incompatible datatypes' % task.name
                )


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInclude, 'include', api_ver=2, builtin=True)
