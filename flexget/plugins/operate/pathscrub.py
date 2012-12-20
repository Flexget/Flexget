from __future__ import unicode_literals, division, absolute_import
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

    def on_task_start(self, task, config):
        # Change path scrub os mode
        pathscrub.os_mode = config

    def on_task_exit(self, task, config):
        # Reset os mode when task has finished
        pathscrub.os_mode = None

    on_task_abort = on_task_exit


plugin.register_plugin(PathScrub, 'pathscrub', api_ver=2)
