import os

import yaml
from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more, process_config
from flexget.event import event
from flexget.utils.tools import MergeException

plugin_name = 'include'
logger = logger.bind(name=plugin_name)


class PluginInclude:
    """Include configuration from another yaml file.

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
            with open(file, encoding='utf-8') as inc_file:
                include = yaml.safe_load(inc_file)
                inc_file.flush()
            errors = process_config(include, plugin.plugin_schemas(interface='task'))
            if errors:
                logger.error('Included file {} has invalid config:', file)
                for error in errors:
                    logger.error('[{}] {}', error.json_pointer, error.message)
                task.abort(f'Invalid config in included file {file}')

            logger.debug('Merging {} into task {}', file, task.name)
            # merge
            try:
                task.merge_config(include)
            except MergeException:
                raise plugin.PluginError(
                    f'Failed to merge include file to task {task.name}, incompatible datatypes'
                )


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInclude, 'include', api_ver=2, builtin=True)
