from __future__ import unicode_literals, division, absolute_import
import logging
import sys
import os
from flexget.plugin import register_plugin

log = logging.getLogger('change')
found_deprecated = False


class ChangeWarn(object):
    """
        Gives warning if user has deprecated / changed configuration in the root level.

        Will be replaced by root level validation in the future!

        Contains ugly hacks, better to include all deprecation warnings here during 1.0 BETA phase
    """

    def __init__(self):
        self.warned = False
        self.executed = False

    def on_process_start(self, task):
        # Run only once
        if self.executed:
            return

        self.executed = True
        found_deprecated = False
        config = task.manager.config

        if 'imdb_queue_input' in task.config:
            log.critical('imdb_queue_input was renamed to emit_imdb_queue')
            found_deprecated = True

        if 'emit_imdb_queue' in task.config:
            log.critical('emit_imdb_queue was renamed to emit_movie_queue, please update your config')
            found_deprecated = True

        if 'imdb_watchlist' in task.config:
            log.critical('imdb_watchlist was renamed to more generic imdb_list, please update your config')
            found_deprecated = True

        if 'transmissionrpc' in task.config:
            log.critical('transmissionrpc was renamed to transmission')
            found_deprecated = True

        if 'torrent_size' in task.config:
            log.critical('Plugin torrent_size is deprecated, use content_size instead')
            found_deprecated = True

        if 'nzb_size' in task.config:
            log.critical('Plugin nzb_size is deprecated, use content_size instead')
            found_deprecated = True

        if 'imdb_queue' in task.config:
            log.critical('Plugin imdb_queue has been replaced by movie_queue, update your config')
            found_deprecated = True

        # priority (dict) was renamed to plugin_priority
        if isinstance(task.config.get('priority', None), dict):
            log.critical('Plugin \'priority\' was renamed to \'plugin_priority\'')

        if found_deprecated:
            task.manager.disable_tasks()
            task.abort('Deprecated config.')

register_plugin(ChangeWarn, 'change_warn', builtin=True)

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

                from flexget import __version__ as version
                if version == '{git}':
                    log.critical('')
                    log.critical('           If you are using bootstrapped git checkout you can run:')
                    log.critical('           bin/paver clean_compiled')

                log.critical('')
                log.critical('-' * 79)
                found_deprecated = True
                break

except:
    pass
