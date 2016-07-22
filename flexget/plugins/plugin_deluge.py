from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import native

import base64
import glob
import logging
import pkg_resources
import os
import re
import sys
import time
import warnings

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub

log = logging.getLogger('deluge')


def add_deluge_windows_install_dir_to_sys_path():
    # Deluge does not install to python system on Windows, add the install directory to sys.path if it is found
    if not (sys.platform.startswith('win') or os.environ.get('ProgramFiles')):
        return
    deluge_dir = os.path.join(os.environ['ProgramFiles'], 'Deluge')
    log.debug('Looking for deluge install in %s' % deluge_dir)
    if not os.path.isdir(deluge_dir):
        return
    deluge_egg = glob.glob(os.path.join(deluge_dir, 'deluge-*-py2.?.egg'))
    if not deluge_egg:
        return
    minor_version = int(re.search(r'py2\.(\d).egg', deluge_egg[0]).group(1))
    if minor_version != sys.version_info[1]:
        log.verbose('Cannot use deluge from install directory because its python version doesn\'t match.')
        return
    log.debug('Found deluge install in %s adding to sys.path' % deluge_dir)
    sys.path.append(deluge_dir)
    for item in os.listdir(deluge_dir):
        if item.endswith(('.egg', '.zip')):
            sys.path.append(os.path.join(deluge_dir, item))


add_deluge_windows_install_dir_to_sys_path()


def install_pausing_reactor():
    class PausingReactor(SelectReactor):
        """A SelectReactor that can be paused and resumed."""

        def __init__(self):
            SelectReactor.__init__(self)
            self.paused = False
            self._return_value = None
            self._release_requested = False
            self._mainLoopGen = None

            # Older versions of twisted do not have the _started attribute, make it a synonym for running in that case
            if not hasattr(self, '_started'):
                PausingReactor._started = property(lambda self: self.running)

        def _mainLoopGenerator(self):
            """Generator that acts as mainLoop, but yields when requested."""
            while self._started:
                try:
                    while self._started:
                        if self._release_requested:
                            self._release_requested = False
                            self.paused = True
                            yield self._return_value
                            self.paused = False
                        self.iterate()
                except KeyboardInterrupt:
                    # Keyboard interrupt pauses the reactor
                    self.pause()
                except GeneratorExit:
                    # GeneratorExit means stop the generator; Do it cleanly by stopping the whole reactor.
                    log.debug('Got GeneratorExit, stopping reactor.', exc_info=True)
                    self.paused = False
                    self.stop()
                except Exception:
                    twisted_log.msg("Unexpected error in main loop.")
                    twisted_log.err()
                else:
                    twisted_log.msg('Main loop terminated.')

        def run(self, installSignalHandlers=False):
            """Starts or resumes the reactor."""
            if not self._started:
                self.startRunning(installSignalHandlers)
                self._mainLoopGen = self._mainLoopGenerator()
            try:
                return next(self._mainLoopGen)
            except StopIteration:
                pass

        def pause(self, return_value=None):
            """Causes reactor to pause after this iteration.
            If :return_value: is specified, it will be returned by the reactor.run call."""
            self._return_value = return_value
            self._release_requested = True

        def stop(self):
            """Stops the reactor."""
            SelectReactor.stop(self)
            # If this was called while the reactor was paused we have to resume in order for it to complete
            if self.paused:
                self.run()

            # These need to be re-registered so that the PausingReactor can be safely restarted after a stop
            self.addSystemEventTrigger('during', 'shutdown', self.crash)
            self.addSystemEventTrigger('during', 'shutdown', self.disconnectAll)

    # Configure twisted to use the PausingReactor.
    installReactor(PausingReactor())

    @event('manager.shutdown')
    def stop_reactor(manager):
        """Shut down the twisted reactor after all tasks have run."""
        if not reactor._stopped:
            log.debug('Stopping twisted reactor.')
            reactor.stop()


# Some twisted import is throwing a warning see #2434
warnings.filterwarnings('ignore', message='Not importing directory .*')

try:
    from twisted.python import log as twisted_log
    from twisted.internet.main import installReactor
    from twisted.internet.selectreactor import SelectReactor
except ImportError:
    # If twisted is not found, errors will be shown later
    pass
else:
    install_pausing_reactor()
try:
    # These have to wait until reactor has been installed to import
    from twisted.internet import reactor
    from deluge.ui.client import client
    from deluge.ui.common import get_localhost_auth
except (ImportError, pkg_resources.DistributionNotFound):
    # If deluge is not found, errors will be shown later
    pass


class DelugePlugin(object):
    """Base class for deluge plugins, contains settings and methods for connecting to a deluge daemon."""

    def on_task_start(self, task, config):
        """Raise a DependencyError if our dependencies aren't available"""
        try:
            from deluge.ui.client import client
        except ImportError as e:
            log.debug('Error importing deluge: %s' % e)
            raise plugin.DependencyError('deluge', 'deluge',
                                         'Deluge >=1.2 module and it\'s dependencies required. ImportError: %s' % e,
                                         log)
        try:
            from twisted.internet import reactor
        except:
            raise plugin.DependencyError('deluge', 'twisted.internet', 'Twisted.internet package required', log)

    def on_task_abort(self, task, config):
        pass

    def prepare_connection_info(self, config):
        config.setdefault('host', 'localhost')
        config.setdefault('port', 58846)
        if 'user' in config or 'pass' in config:
            warnings.warn('deluge `user` and `pass` options have been renamed `username` and `password`',
                          DeprecationWarning)
            config.setdefault('username', config.get('user', ''))
            config.setdefault('password', config.get('pass', ''))
        config.setdefault('username', '')
        config.setdefault('password', '')

    def on_disconnect(self):
        """Pauses the reactor. Gets called when we disconnect from the daemon."""
        # pause the reactor, so flexget can continue
        reactor.callLater(0, reactor.pause)

    def on_connect_fail(self, result):
        """Pauses the reactor, returns PluginError. Gets called when connection to deluge daemon fails."""
        log.debug('Connect to deluge daemon failed, result: %s' % result)
        reactor.callLater(0, reactor.pause, plugin.PluginError('Could not connect to deluge daemon', log))

    def on_connect_success(self, result, task, config):
        """Gets called when successfully connected to the daemon. Should do the work then call client.disconnect"""
        raise NotImplementedError

    def connect(self, task, config):
        """Connects to the deluge daemon and runs on_connect_success """

        if config['host'] in ['localhost', '127.0.0.1'] and not config.get('username'):
            # If an username is not specified, we have to do a lookup for the localclient username/password
            auth = get_localhost_auth()
            if auth[0]:
                config['username'], config['password'] = auth
            else:
                raise plugin.PluginError('Unable to get local authentication info for Deluge. You may need to '
                                         'specify an username and password from your Deluge auth file.')

        client.set_disconnect_callback(self.on_disconnect)

        d = client.connect(
            host=config['host'],
            port=config['port'],
            username=config['username'],
            password=config['password'])

        d.addCallback(self.on_connect_success, task, config).addErrback(self.on_connect_fail)
        result = reactor.run()
        if isinstance(result, Exception):
            raise result
        return result


class InputDeluge(DelugePlugin):
    """Create entries for torrents in the deluge session."""
    #
    settings_map = {
        'name': 'title',
        'hash': 'torrent_info_hash',
        'num_peers': 'torrent_peers',
        'num_seeds': 'torrent_seeds',
        'progress': 'deluge_progress',
        'seeding_time': ('deluge_seed_time', lambda time: time / 3600),
        'private': 'deluge_private',
        'state': 'deluge_state',
        'eta': 'deluge_eta',
        'ratio': 'deluge_ratio',
        'move_on_completed_path': 'deluge_movedone',
        'save_path': 'deluge_path',
        'label': 'deluge_label',
        'total_size': ('content_size', lambda size: size / 1024 / 1024),
        'files': ('content_files', lambda file_dicts: [f['path'] for f in file_dicts])}

    def __init__(self):
        self.entries = []

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'config_path': {'type': 'string', 'format': 'path'},
                    'filter': {
                        'type': 'object',
                        'properties': {
                            'label': {'type': 'string'},
                            'state': {
                                'type': 'string',
                                'enum': ['active', 'downloading', 'seeding', 'queued', 'paused']
                            }
                        },
                        'additionalProperties': False
                    }
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        if 'filter' in config:
            filter = config['filter']
            if 'label' in filter:
                filter['label'] = filter['label'].lower()
            if 'state' in filter:
                filter['state'] = filter['state'].capitalize()
        self.prepare_connection_info(config)
        return config

    def on_task_input(self, task, config):
        """Generates and returns a list of entries from the deluge daemon."""
        # Reset the entries list
        self.entries = []
        # Call connect, entries get generated if everything is successful
        self.connect(task, self.prepare_config(config))
        return self.entries

    def on_connect_success(self, result, task, config):
        """Creates a list of FlexGet entries from items loaded in deluge and stores them to self.entries"""
        from deluge.ui.client import client

        def on_get_torrents_status(torrents):
            config_path = os.path.expanduser(config.get('config_path', ''))
            for hash, torrent_dict in torrents.items():
                # Make sure it has a url so no plugins crash
                entry = Entry(deluge_id=hash, url='')
                if config_path:
                    torrent_path = os.path.join(config_path, 'state', hash + '.torrent')
                    if os.path.isfile(torrent_path):
                        entry['location'] = torrent_path
                        if not torrent_path.startswith('/'):
                            torrent_path = '/' + torrent_path
                        entry['url'] = 'file://' + torrent_path
                    else:
                        log.warning('Did not find torrent file at %s' % torrent_path)
                for key, value in torrent_dict.items():
                    flexget_key = self.settings_map[key]
                    if isinstance(flexget_key, tuple):
                        flexget_key, format_func = flexget_key
                        value = format_func(value)
                    entry[flexget_key] = value
                self.entries.append(entry)
            client.disconnect()

        filter = config.get('filter', {})
        # deluge client lib chokes on future's newlist, make sure we have a native python list here
        client.core.get_torrents_status(filter, native(list(self.settings_map.keys()))).addCallback(
            on_get_torrents_status)


class OutputDeluge(DelugePlugin):
    """Add the torrents directly to deluge, supporting custom save paths."""
    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'path': {'type': 'string'},
                    'movedone': {'type': 'string'},
                    'label': {'type': 'string'},
                    'queuetotop': {'type': 'boolean'},
                    'automanaged': {'type': 'boolean'},
                    'maxupspeed': {'type': 'number'},
                    'maxdownspeed': {'type': 'number'},
                    'maxconnections': {'type': 'integer'},
                    'maxupslots': {'type': 'integer'},
                    'ratio': {'type': 'number'},
                    'removeatratio': {'type': 'boolean'},
                    'addpaused': {'type': 'boolean'},
                    'compact': {'type': 'boolean'},
                    'content_filename': {'type': 'string'},
                    'main_file_only': {'type': 'boolean'},
                    'main_file_ratio': {'type': 'number'},
                    'magnetization_timeout': {'type': 'integer'},
                    'keep_subs': {'type': 'boolean'},
                    'hide_sparse_files': {'type': 'boolean'},
                    'enabled': {'type': 'boolean'},
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        self.prepare_connection_info(config)
        config.setdefault('enabled', True)
        config.setdefault('path', '')
        config.setdefault('movedone', '')
        config.setdefault('label', '')
        config.setdefault('main_file_ratio', 0.90)
        config.setdefault('magnetization_timeout', 0)
        config.setdefault('keep_subs', True)  # does nothing without 'content_filename' or 'main_file_only' enabled
        config.setdefault('hide_sparse_files', False)  # does nothing without 'main_file_only' enabled
        return config

    def __init__(self):
        self.deluge_version = None
        self.options = {'maxupspeed': 'max_upload_speed', 'maxdownspeed': 'max_download_speed',
                        'maxconnections': 'max_connections', 'maxupslots': 'max_upload_slots',
                        'automanaged': 'auto_managed', 'ratio': 'stop_ratio', 'removeatratio': 'remove_at_ratio',
                        'addpaused': 'add_paused', 'compact': 'compact_allocation'}

    @plugin.priority(120)
    def on_task_download(self, task, config):
        """
        Call download plugin to generate the temp files we will load into deluge
        then verify they are valid torrents
        """
        import deluge.ui.common
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            for entry in task.accepted:
                if not entry.get('deluge_id'):
                    download.instance.get_temp_file(task, entry, handle_magnets=True)

        # Check torrent files are valid
        for entry in task.accepted:
            if os.path.exists(entry.get('file', '')):
                # Check if downloaded file is a valid torrent file
                try:
                    deluge.ui.common.TorrentInfo(entry['file'])
                except Exception:
                    entry.fail('Invalid torrent file')
                    log.error('Torrent file appears invalid for: %s', entry['title'])

    @plugin.priority(135)
    def on_task_output(self, task, config):
        """Add torrents to deluge at exit."""
        config = self.prepare_config(config)
        # don't add when learning
        if task.options.learn:
            return
        if not config['enabled'] or not (task.accepted or task.options.test):
            return

        self.connect(task, config)
        # Clean up temp file if download plugin is not configured for this task
        if 'download' not in task.config:
            for entry in task.accepted + task.failed:
                if os.path.exists(entry.get('file', '')):
                    os.remove(entry['file'])
                    del (entry['file'])

    def on_connect_success(self, result, task, config):
        """Gets called when successfully connected to a daemon."""
        from deluge.ui.client import client
        from twisted.internet import reactor, defer

        if not result:
            log.debug('on_connect_success returned a failed result. BUG?')

        if task.options.test:
            log.debug('Test connection to deluge daemon successful.')
            client.disconnect()
            return

        def format_label(label):
            """Makes a string compliant with deluge label naming rules"""
            return re.sub('[^\w-]+', '_', label.lower())

        def set_torrent_options(torrent_id, entry, opts):
            """Gets called when a torrent was added to the daemon."""
            dlist = []
            if not torrent_id:
                log.error('There was an error adding %s to deluge.' % entry['title'])
                # TODO: Fail entry? How can this happen still now?
                return
            log.info('%s successfully added to deluge.' % entry['title'])
            entry['deluge_id'] = torrent_id

            def create_path(result, path):
                """Creates the specified path if deluge is older than 1.3"""
                from deluge.common import VersionSplit
                # Before 1.3, deluge would not create a non-existent move directory, so we need to.
                if VersionSplit('1.3.0') > VersionSplit(self.deluge_version):
                    if client.is_localhost():
                        if not os.path.isdir(path):
                            log.debug('path %s doesn\'t exist, creating' % path)
                            os.makedirs(path)
                    else:
                        log.warning('If path does not exist on the machine running the daemon, move will fail.')

            if opts.get('movedone'):
                dlist.append(version_deferred.addCallback(create_path, opts['movedone']))
                dlist.append(client.core.set_torrent_move_completed(torrent_id, True))
                dlist.append(client.core.set_torrent_move_completed_path(torrent_id, opts['movedone']))
                log.debug('%s move on complete set to %s' % (entry['title'], opts['movedone']))
            if opts.get('label'):
                def apply_label(result, torrent_id, label):
                    """Gets called after labels and torrent were added to deluge."""
                    return client.label.set_torrent(torrent_id, label)

                dlist.append(label_deferred.addCallback(apply_label, torrent_id, opts['label']))
            if opts.get('queuetotop') is not None:
                if opts['queuetotop']:
                    dlist.append(client.core.queue_top([torrent_id]))
                    log.debug('%s moved to top of queue' % entry['title'])
                else:
                    dlist.append(client.core.queue_bottom([torrent_id]))
                    log.debug('%s moved to bottom of queue' % entry['title'])

            def on_get_torrent_status(status):
                """Gets called with torrent status, including file info.
                Sets the torrent options which require knowledge of the current status of the torrent."""

                main_file_dlist = []

                # Determine where the file should be
                move_now_path = None
                if opts.get('movedone'):
                    if status['progress'] == 100:
                        move_now_path = opts['movedone']
                    else:
                        # Deluge will unset the move completed option if we move the storage, forgo setting proper
                        # path, in favor of leaving proper final location.
                        log.debug('Not moving storage for %s, as this will prevent movedone.' % entry['title'])
                elif opts.get('path'):
                    move_now_path = opts['path']

                if move_now_path and os.path.normpath(move_now_path) != os.path.normpath(status['save_path']):
                    main_file_dlist.append(version_deferred.addCallback(create_path, move_now_path))
                    log.debug('Moving storage for %s to %s' % (entry['title'], move_now_path))
                    main_file_dlist.append(client.core.move_storage([torrent_id], move_now_path))

                if opts.get('content_filename') or opts.get('main_file_only'):

                    def file_exists(filename):
                        # Checks the download path as well as the move completed path for existence of the file
                        if os.path.exists(os.path.join(status['save_path'], filename)):
                            return True
                        elif status.get('move_on_completed') and status.get('move_on_completed_path'):
                            if os.path.exists(os.path.join(status['move_on_completed_path'], filename)):
                                return True
                        else:
                            return False

                    def unused_name(name):
                        # If on local computer, tries appending a (#) suffix until a unique filename is found
                        if client.is_localhost():
                            counter = 2
                            while file_exists(name):
                                name = ''.join([os.path.splitext(name)[0],
                                                " (", str(counter), ')',
                                                os.path.splitext(name)[1]])
                                counter += 1
                        else:
                            log.debug('Cannot ensure content_filename is unique '
                                      'when adding to a remote deluge daemon.')
                        return name

                    def rename(file, new_name):
                        # Renames a file in torrent
                        main_file_dlist.append(
                            client.core.rename_files(torrent_id,
                                                     [(file['index'], new_name)]))
                        log.debug('File %s in %s renamed to %s' % (file['path'], entry['title'], new_name))

                    # find a file that makes up more than main_file_ratio (default: 90%) of the total size
                    main_file = None
                    for file in status['files']:
                        if file['size'] > (status['total_size'] * opts.get('main_file_ratio')):
                            main_file = file
                            break

                    if main_file is not None:
                        # proceed with renaming only if such a big file is found

                        # find the subtitle file
                        keep_subs = opts.get('keep_subs')
                        sub_file = None
                        if keep_subs:
                            sub_exts = [".srt", ".sub"]
                            for file in status['files']:
                                ext = os.path.splitext(file['path'])[1]
                                if ext in sub_exts:
                                    sub_file = file
                                    break

                        # check for single file torrents so we dont add unnecessary folders
                        if (os.path.dirname(main_file['path']) is not ("" or "/")):
                            # check for top folder in user config
                            if (opts.get('content_filename') and os.path.dirname(opts['content_filename']) is not ""):
                                top_files_dir = os.path.dirname(opts['content_filename']) + "/"
                            else:
                                top_files_dir = os.path.dirname(main_file['path']) + "/"
                        else:
                            top_files_dir = "/"

                        if opts.get('content_filename'):
                            # rename the main file
                            big_file_name = (top_files_dir +
                                             os.path.basename(opts['content_filename']) +
                                             os.path.splitext(main_file['path'])[1])
                            big_file_name = unused_name(big_file_name)
                            rename(main_file, big_file_name)

                            # rename subs along with the main file
                            if sub_file is not None and keep_subs:
                                sub_file_name = (os.path.splitext(big_file_name)[0] +
                                                 os.path.splitext(sub_file['path'])[1])
                                rename(sub_file, sub_file_name)

                        if opts.get('main_file_only'):
                            # download only the main file (and subs)
                            file_priorities = [1 if f == main_file or (f == sub_file and keep_subs) else 0
                                               for f in status['files']]
                            main_file_dlist.append(
                                client.core.set_torrent_file_priorities(torrent_id, file_priorities))

                            if opts.get('hide_sparse_files'):
                                # hide the other sparse files that are not supposed to download but are created anyway
                                # http://dev.deluge-torrent.org/ticket/1827
                                # Made sparse files behave better with deluge http://flexget.com/ticket/2881
                                sparse_files = [f for f in status['files']
                                                if f != main_file and (f != sub_file or (not keep_subs))]
                                rename_pairs = [(f['index'],
                                                 top_files_dir + ".sparse_files/" + os.path.basename(f['path']))
                                                for f in sparse_files]
                                main_file_dlist.append(client.core.rename_files(torrent_id, rename_pairs))
                    else:
                        log.warning('No files in "%s" are > %d%% of content size, no files renamed.' % (
                            entry['title'],
                            opts.get('main_file_ratio') * 100))

                return defer.DeferredList(main_file_dlist)

            status_keys = ['files', 'total_size', 'save_path', 'move_on_completed_path',
                           'move_on_completed', 'progress']
            dlist.append(client.core.get_torrent_status(torrent_id, status_keys).addCallback(on_get_torrent_status))

            return defer.DeferredList(dlist)

        def on_fail(result, task, entry):
            """Gets called when daemon reports a failure adding the torrent."""
            log.info('%s was not added to deluge! %s' % (entry['title'], result))
            entry.fail('Could not be added to deluge')

        # dlist is a list of deferreds that must complete before we exit
        dlist = []
        # loop through entries to get a list of labels to add
        labels = set([format_label(entry['label']) for entry in task.accepted if entry.get('label')])
        if config.get('label'):
            labels.add(format_label(config['label']))
        label_deferred = defer.succeed(True)
        if labels:
            # Make sure the label plugin is available and enabled, then add appropriate labels

            def on_get_enabled_plugins(plugins):
                """Gets called with the list of enabled deluge plugins."""

                def on_label_enabled(result):
                    """ This runs when we verify the label plugin is enabled. """

                    def on_get_labels(d_labels):
                        """Gets available labels from deluge, and adds any new labels we need."""
                        dlist = []
                        for label in labels:
                            if label not in d_labels:
                                log.debug('Adding the label %s to deluge' % label)
                                dlist.append(client.label.add(label))
                        return defer.DeferredList(dlist)

                    return client.label.get_labels().addCallback(on_get_labels)

                if 'Label' in plugins:
                    return on_label_enabled(True)
                else:
                    # Label plugin isn't enabled, so we check if it's available and enable it.

                    def on_get_available_plugins(plugins):
                        """Gets plugins available to deluge, enables Label plugin if available."""
                        if 'Label' in plugins:
                            log.debug('Enabling label plugin in deluge')
                            return client.core.enable_plugin('Label').addCallback(on_label_enabled)
                        else:
                            log.error('Label plugin is not installed in deluge')

                    return client.core.get_available_plugins().addCallback(on_get_available_plugins)

            label_deferred = client.core.get_enabled_plugins().addCallback(on_get_enabled_plugins)
            dlist.append(label_deferred)

        def on_get_daemon_info(ver):
            """Gets called with the daemon version info, stores it in self."""
            log.debug('deluge version %s' % ver)
            self.deluge_version = ver

        version_deferred = client.daemon.info().addCallback(on_get_daemon_info)
        dlist.append(version_deferred)

        def on_get_session_state(torrent_ids):
            """Gets called with a list of torrent_ids loaded in the deluge session.
            Adds new torrents and modifies the settings for ones already in the session."""
            dlist = []
            # add the torrents
            for entry in task.accepted:

                @defer.inlineCallbacks
                def _wait_for_metadata(torrent_id, timeout):
                    log.verbose('Waiting %d seconds for "%s" to magnetize' % (timeout, entry['title']))
                    for _ in range(timeout):
                        time.sleep(1)
                        try:
                            status = yield client.core.get_torrent_status(torrent_id, ['files'])
                        except Exception as err:
                            log.error('wait_for_metadata Error: %s' % err)
                            break
                        if len(status['files']) > 0:
                            log.info('"%s" magnetization successful' % (entry['title']))
                            break
                    else:
                        log.warning('"%s" did not magnetize before the timeout elapsed, '
                                    'file list unavailable for processing.' % entry['title'])

                    defer.returnValue(torrent_id)

                def add_entry(entry, opts):
                    """Adds an entry to the deluge session"""
                    magnet, filedump = None, None
                    if entry.get('url', '').startswith('magnet:'):
                        magnet = entry['url']
                    else:
                        if not os.path.exists(entry['file']):
                            entry.fail('Downloaded temp file \'%s\' doesn\'t exist!' % entry['file'])
                            del (entry['file'])
                            return
                        with open(entry['file'], 'rb') as f:
                            filedump = base64.encodestring(f.read())

                    log.verbose('Adding %s to deluge.' % entry['title'])
                    if magnet:
                        d = client.core.add_torrent_magnet(magnet, opts)
                        if config.get('magnetization_timeout'):
                            d.addCallback(_wait_for_metadata, config['magnetization_timeout'])
                        return d
                    else:
                        return client.core.add_torrent_file(entry['title'], filedump, opts)

                # Generate deluge options dict for torrent add
                add_opts = {}
                try:
                    path = entry.render(entry.get('path', config['path']))
                    if path:
                        add_opts['download_location'] = pathscrub(os.path.expanduser(path))
                except RenderError as e:
                    log.error('Could not set path for %s: %s' % (entry['title'], e))
                for fopt, dopt in self.options.items():
                    value = entry.get(fopt, config.get(fopt))
                    if value is not None:
                        add_opts[dopt] = value
                        if fopt == 'ratio':
                            add_opts['stop_at_ratio'] = True
                # Make another set of options, that get set after the torrent has been added
                modify_opts = {
                    'label': format_label(entry.get('label', config['label'])),
                    'queuetotop': entry.get('queuetotop', config.get('queuetotop')),
                    'main_file_only': entry.get('main_file_only', config.get('main_file_only', False)),
                    'main_file_ratio': entry.get('main_file_ratio', config.get('main_file_ratio')),
                    'hide_sparse_files': entry.get('hide_sparse_files', config.get('hide_sparse_files', True)),
                    'keep_subs': entry.get('keep_subs', config.get('keep_subs', True))
                }
                try:
                    movedone = entry.render(entry.get('movedone', config['movedone']))
                    modify_opts['movedone'] = pathscrub(os.path.expanduser(movedone))
                except RenderError as e:
                    log.error('Error setting movedone for %s: %s' % (entry['title'], e))
                try:
                    content_filename = entry.get('content_filename', config.get('content_filename', ''))
                    modify_opts['content_filename'] = pathscrub(entry.render(content_filename))
                except RenderError as e:
                    log.error('Error setting content_filename for %s: %s' % (entry['title'], e))

                torrent_id = entry.get('deluge_id') or entry.get('torrent_info_hash')
                torrent_id = torrent_id and torrent_id.lower()
                if torrent_id in torrent_ids:
                    log.info('%s is already loaded in deluge, setting options' % entry['title'])
                    # Entry has a deluge id, verify the torrent is still in the deluge session and apply options
                    # Since this is already loaded in deluge, we may also need to change the path
                    modify_opts['path'] = add_opts.pop('download_location', None)
                    dlist.extend([set_torrent_options(torrent_id, entry, modify_opts),
                                  client.core.set_torrent_options([torrent_id], add_opts)])
                else:
                    dlist.append(add_entry(entry, add_opts).addCallbacks(
                        set_torrent_options, on_fail, callbackArgs=(entry, modify_opts), errbackArgs=(task, entry)))
            return defer.DeferredList(dlist)

        dlist.append(client.core.get_session_state().addCallback(on_get_session_state))

        def on_complete(result):
            """Gets called when all of our tasks for deluge daemon are complete."""
            client.disconnect()

        tasks = defer.DeferredList(dlist).addBoth(on_complete)

        def on_timeout(result):
            """Gets called if tasks have not completed in 30 seconds.
            Should only happen when something goes wrong."""
            log.error('Timed out while adding torrents to deluge.')
            log.debug('dlist: %s' % result.resultList)
            client.disconnect()

        # Schedule a disconnect to happen if FlexGet hangs while connected to Deluge
        # Leave the timeout long, to give time for possible lookups to occur
        reactor.callLater(600, lambda: tasks.called or on_timeout(tasks))

    def on_task_exit(self, task, config):
        """Make sure all temp files are cleaned up when task exits"""
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    def on_task_abort(self, task, config):
        """Make sure normal cleanup tasks still happen on abort."""
        DelugePlugin.on_task_abort(self, task, config)
        self.on_task_exit(task, config)


@event('plugin.register')
def register_plugin():
    plugin.register(InputDeluge, 'from_deluge', api_ver=2)
    plugin.register(OutputDeluge, 'deluge', api_ver=2)
