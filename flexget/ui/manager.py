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
            # Write empty feeds and presets to the config
            newconfig.write(yaml.dump({'presets': {}, 'feeds': {}}))
            newconfig.close()
            self.load_config(config_filename)

    def execute(self, *args, **kwargs):
        # Update feed instances to match config
        self.update_feeds()
        Manager.execute(self, *args, **kwargs)

    def update_feeds(self):
        """Updates instances of all configured feeds from config"""
        from flexget.feed import Feed

        if not isinstance(self.config['feeds'], dict):
            log.critical('Feeds is in wrong datatype, please read configuration guides')
            return

        # construct feed list
        for name in self.config.get('feeds', {}):
            if not isinstance(self.config['feeds'][name], dict):
                continue
            if name in self.feeds:
                # This feed already has an instance, update it
                self.feeds[name].config = deepcopy(self.config['feeds'][name])
                if not name.startswith('_'):
                    self.feeds[name].enabled = True
            else:
                # Create feed
                feed = Feed(self, name, deepcopy(self.config['feeds'][name]))
                # If feed name is prefixed with _ it's disabled
                if name.startswith('_'):
                    feed.enabled = False
                self.feeds[name] = feed
        # Delete any feed instances that are no longer in the config
        for name in [n for n in self.feeds if n not in self.config['feeds']]:
            del self.feeds[name]

    def check_lock(self):
        if self.options.autoreload:
            log.info('autoreload enabled, not checking for lock file')
            return False
        return Manager.check_lock(self)
