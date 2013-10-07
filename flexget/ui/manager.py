from __future__ import unicode_literals, division, absolute_import
import os
import sys
import logging
import yaml
from flexget.manager import Manager

log = logging.getLogger('ui.manager')


class UIManager(Manager):

    def find_config(self):
        """If no config file is found by the webui, a blank one is created."""
        try:
            super(UIManager, self).find_config()
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
            # Call superclass again to find our newly created file
            super(UIManager, self).find_config()

    # TODO: Remove? Don't think we need this anymore.
    def __check_lock(self):
        if self.options.autoreload:
            log.info('autoreload enabled, not checking for lock file')
            return False
        return Manager.check_lock(self)
