from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import sys

from flexget import plugin
from flexget.event import event

log = logging.getLogger('change')
found_deprecated = False


class ChangeWarn(object):
    """
        Gives warning if user has deprecated / changed configuration in the root level.

        Will be replaced by root level validation in the future!

        Contains ugly hacks, better to include all deprecation warnings here during 1.0 BETA phase
    """

    def on_task_start(self, task, config):
        global found_deprecated

        if 'torrent_size' in task.config:
            log.critical('Plugin torrent_size is deprecated, use content_size instead')
            found_deprecated = True

        if 'nzb_size' in task.config:
            log.critical('Plugin nzb_size is deprecated, use content_size instead')
            found_deprecated = True

        if found_deprecated:
            task.manager.shutdown(finish_queue=False)
            task.abort('Deprecated config.')


@event('plugin.register')
def register_plugin():
    plugin.register(ChangeWarn, 'change_warn', builtin=True, api_ver=2)


# check that no old plugins are in pre-compiled form (pyc)
try:
    import os.path
    plugin_dirs = (os.path.normpath(sys.path[0] + '/../flexget/plugins/'),
                   os.path.normpath(sys.path[0] + '/../flexget/plugins/input/'))
    for plugin_dir in plugin_dirs:
        for name in os.listdir(plugin_dir):
            require_clean = False

            if name.startswith('module'):
                require_clean = True

            if name == 'csv.pyc':
                require_clean = True

            if 'resolver' in name:
                require_clean = True

            if 'filter_torrent_size' in name:
                require_clean = True

            if 'filter_nzb_size' in name:
                require_clean = True

            if 'module_priority' in name:
                require_clean = True

            if 'ignore_feed' in name:
                require_clean = True

            if 'module_manual' in name:
                require_clean = True

            if 'output_exec' in name:
                require_clean = True

            if 'plugin_adv_exec' in name:
                require_clean = True

            if 'output_transmissionrpc' in name:
                require_clean = True

            if require_clean:
                log.critical('-' * 79)
                log.critical('IMPORTANT: Your installation has some files from older FlexGet!')
                log.critical('')
                log.critical('           Please remove all pre-compiled .pyc and .pyo files from %s' % plugin_dir)
                log.critical('           Offending file: %s' % name)
                log.critical('')
                log.critical('           After getting rid of these FlexGet should run again normally')

                log.critical('')
                log.critical('-' * 79)
                found_deprecated = True
                break

except:
    pass
