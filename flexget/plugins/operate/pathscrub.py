from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.utils import pathscrub


class PathScrub(object):
    """
    Plugin that will clear illegal characters from paths. Other plugins should use this if available when
    creating paths. User can specify what os if filenames must be compatible with an os other than current.

    Example::
      pathscrub: windows
    """

    schema = {'type': 'string', 'enum': ['windows', 'linux', 'mac']}

    def on_task_start(self, task, config):
        # Change path scrub os mode
        pathscrub.os_mode = config

    def on_task_exit(self, task, config):
        # Reset os mode when task has finished
        pathscrub.os_mode = None

    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(PathScrub, 'pathscrub', api_ver=2)
