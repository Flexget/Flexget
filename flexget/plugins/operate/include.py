from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import io
import logging
import os

import yaml
from sqlalchemy import Column, Integer, Unicode

from flexget import plugin, db_schema
from flexget.config_schema import one_or_more, process_config
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import MergeException, merge_dict_from_to, get_config_hash

plugin_name = 'include'
log = logging.getLogger(plugin_name)
Base = db_schema.versioned_base(plugin_name, 0)


class LastHash(Base):
    __tablename__ = 'include_last_hash'

    id = Column(Integer, primary_key=True)
    task = Column(Unicode)
    file = Column(Unicode)
    hash = Column(Unicode)


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
        if isinstance(config, str):
            files = [config]

        for file_name in files:
            file_name = os.path.expanduser(file_name)
            if not os.path.isabs(file_name):
                file_name = os.path.join(task.manager.config_base, file_name)
            with io.open(file_name, encoding='utf-8') as inc_file:
                include = yaml.load(inc_file)
                inc_file.flush()
            errors = process_config(include, plugin.plugin_schemas(interface='task'))
            if errors:
                log.error('Included file %s has invalid config:', file_name)
                for error in errors:
                    log.error('[%s] %s', error.json_pointer, error.message)
                task.abort('Invalid config in included file %s' % file_name)

            new_hash = str(get_config_hash(include))
            with Session() as session:
                last_hash = session.query(LastHash).filter(LastHash.task == task.name).filter(
                    LastHash.file == file_name).first()
                if not last_hash:
                    log.debug('no config hash detected for task %s with file %s, creating', task.name, file_name)
                    last_hash = LastHash(task=task.name, file=file_name)
                    session.add(last_hash)
                if last_hash.hash != new_hash:
                    log.debug('new hash detected, triggering config change event')
                    task.config_changed()
                last_hash.hash = new_hash

            log.debug('Merging %s into task %s', file_name, task.name)
            # merge
            try:
                merge_dict_from_to(include, task.config)
            except MergeException:
                raise plugin.PluginError('Failed to merge include file to task %s, incompatible datatypes' % task.name)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInclude, 'include', api_ver=2, builtin=True)
