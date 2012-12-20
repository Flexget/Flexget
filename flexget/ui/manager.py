from __future__ import unicode_literals, division, absolute_import
import os
import sys
import logging
import yaml
from copy import deepcopy
from flexget.manager import Manager
from flexget.ui.options import StoreErrorArgumentParser

log = logging.getLogger('ui.manager')


class UIManager(Manager):

    def __init__(self, options, coreparser):
        Manager.__init__(self, options)
        self.parser = StoreErrorArgumentParser(coreparser)

    def find_config(self):
        """If no config file is found by the webui, a blank one is created."""
        try:
            Manager.find_config(self)
        except IOError:
            # No config file found, create a blank one in the home path
            if sys.platform.startswith('win'):
                # On windows machines do not use a dot in folder name
                folder = 'flexget'
            else:
                folder = '.flexget'
            config_path = os.path.join(os.path.expanduser('~'), folder)
            if not os.path.exists(config_path):
                os.mkdir(config_path)
            config_filename = os.path.join(config_path, self.options.config)
            log.info('Config file %s not found. Creating new config %s' % (self.options.config, config_filename))
            newconfig = file(config_filename, 'w')
            # Write empty tasks and presets to the config
            newconfig.write(yaml.dump({'presets': {}, 'tasks': {}}))
            newconfig.close()
            self.load_config(config_filename)

    def execute(self, *args, **kwargs):
        # Update task instances to match config
        self.update_tasks()
        Manager.execute(self, *args, **kwargs)

    def update_tasks(self):
        """Updates instances of all configured tasks from config"""
        from flexget.task import Task

        if not isinstance(self.config['tasks'], dict):
            log.critical('Tasks is in wrong datatype, please read configuration guides')
            return

        # construct task list
        for name in self.config.get('tasks', {}):
            if not isinstance(self.config['tasks'][name], dict):
                continue
            if name in self.tasks:
                # This task already has an instance, update it
                self.tasks[name].config = deepcopy(self.config['tasks'][name])
                if not name.startswith('_'):
                    self.tasks[name].enabled = True
            else:
                # Create task
                task = Task(self, name, deepcopy(self.config['tasks'][name]))
                # If task name is prefixed with _ it's disabled
                if name.startswith('_'):
                    task.enabled = False
                self.tasks[name] = task
        # Delete any task instances that are no longer in the config
        for name in [n for n in self.tasks if n not in self.config['tasks']]:
            del self.tasks[name]

    def check_lock(self):
        if self.options.autoreload:
            log.info('autoreload enabled, not checking for lock file')
            return False
        return Manager.check_lock(self)
