import sys
import re
import ntpath
from flexget import plugin
from flexget import validator


class PathScrub(object):
    """
    Plugin that will clear illegal characters from paths. Other plugins should use this if available when
    creating paths. User can specify what os if filenames must be compatible with an os other than current.

    Example::
      pathscrub: windows
    """

    replace_maps = {
        'windows': {
            '[:*?"<>| ]+': ' ', # Turn illegal characters into a space
            r'\.\s*([/\\]|$)': r'\1'}, # Dots cannot end file or directory names
        'mac': {
            '[: ]+': ' '},
        'linux': {}} # No replacements on linux

    def __init__(self):
        self.config = None

    def validator(self):
        root = validator.factory('choice')
        root.accept_choices(['windows', 'linux', 'mac'], ignore_case=True)
        return root

    def on_feed_start(self, feed, config):
        # Store config to self so it can be referenced when a plugin calls scrub method
        self.config = config.lower()

    def on_feed_exit(self, feed, config):
        # Reset config when feed has finished
        self.config = None

    on_feed_abort = on_feed_exit

    def scrub(self, dirty_path):
        """
        Strips illegal characters for a given os from a path.

        :param dirty_path: Path to be scrubbed.
        :return: A valid path.
        """

        if self.config:
            # If os is defined, use replacements for that os
            replace_map = self.replace_maps[self.config]
        else:
            # If os is not defined, try to detect appropriate
            drive, path = ntpath.splitdrive(dirty_path)
            if sys.platform.startswith('win') or drive:
                replace_map = self.replace_maps['windows']
            elif sys.platform.startswith('darwin'):
                replace_map = self.replace_maps['mac']
            else:
                replace_map = self.replace_maps['linux']

        # Make sure not to mess with windows drive specifications
        drive, path = ntpath.splitdrive(dirty_path)
        for search, replace in replace_map.iteritems():
            path = re.sub(search, replace, path)

        return drive + path.strip()


plugin.register_plugin(PathScrub, 'pathscrub', api_ver=2)
