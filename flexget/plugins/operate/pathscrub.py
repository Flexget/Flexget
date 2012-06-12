from flexget import plugin
from flexget import validator
from flexget.utils import pathscrub


class PathScrub(object):
    """
    Plugin that will clear illegal characters from paths. Other plugins should use this if available when
    creating paths. User can specify what os if filenames must be compatible with an os other than current.

    Example::
      pathscrub: windows
    """

    def validator(self):
        root = validator.factory('choice')
        root.accept_choices(['windows', 'linux', 'mac'], ignore_case=True)
        return root

    def on_feed_start(self, feed, config):
        # Change path scrub os mode
        pathscrub.os_mode = config

    def on_feed_exit(self, feed, config):
        # Reset os mode when feed has finished
        pathscrub.os_mode = None

    on_feed_abort = on_feed_exit


plugin.register_plugin(PathScrub, 'pathscrub', api_ver=2)
