import base64
import os
import re
import sys
import time

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError

logger = logger.bind(name='deluge')


class DelugePlugin:
    """Base class for deluge plugins, contains settings and methods for connecting to a deluge daemon."""

    def on_task_start(self, task, config):
        """Fail early if we can't import/configure the deluge client."""
        self.setup_client(config)

    def setup_client(self, config):
        try:
            from deluge_client import DelugeRPCClient
        except ImportError as e:
            logger.debug('Error importing deluge-client: {}', e)
            raise plugin.DependencyError(
                'deluge',
                'deluge-client',
                'deluge-client >=1.5 is required. `pip install deluge-client` to install.',
                logger,
            )
        config = self.prepare_config(config)

        if config['host'] in ['localhost', '127.0.0.1'] and not config.get('username'):
            # If an username is not specified, we have to do a lookup for the localclient username/password
            auth = self.get_localhost_auth(config.get('config_path'))
            if auth and auth[0]:
                config['username'], config['password'] = auth
        if not config.get('username') or not config.get('password'):
            raise plugin.PluginError(
                'Unable to get authentication info for Deluge. You may need to '
                'specify an username and password from your Deluge auth file.'
            )

        return DelugeRPCClient(
            config['host'],
            config['port'],
            config['username'],
            config['password'],
            decode_utf8=True,
        )

    def prepare_config(self, config):
        config.setdefault('host', 'localhost')
        config.setdefault('port', 58846)
        return config

    @staticmethod
    def get_localhost_auth(config_path=None):
        if config_path is None:
            if sys.platform.startswith('win'):
                auth_file = os.path.join(os.getenv('APPDATA'), 'deluge', 'auth')
            else:
                auth_file = os.path.expanduser('~/.config/deluge/auth')
        else:
            auth_file = os.path.join(config_path, 'auth')
        if not os.path.isfile(auth_file):
            return None

        with open(auth_file) as auth:
            for line in auth:
                line = line.strip()
                if line.startswith('#') or not line:
                    # This is a comment or blank line
                    continue

                lsplit = line.split(':')
                if lsplit[0] == 'localclient':
                    username, password = lsplit[:2]
                    return username, password


class InputDeluge(DelugePlugin):
    """Create entries for torrents in the deluge session."""

    # Fields we provide outside of the deluge_ prefixed namespace
    settings_map = {
        'name': 'title',
        'hash': 'torrent_info_hash',
        'num_peers': 'torrent_peers',
        'num_seeds': 'torrent_seeds',
        'total_size': ('content_size', lambda size: size / 1024 / 1024),
        'files': ('content_files', lambda file_dicts: [f['path'] for f in file_dicts]),
    }

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
                                'enum': ['active', 'downloading', 'seeding', 'queued', 'paused'],
                            },
                        },
                        'additionalProperties': False,
                    },
                },
                'additionalProperties': False,
            },
        ]
    }

    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        super().on_task_start(task, config)

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {}
        if 'filter' in config:
            filter = config['filter']
            if 'label' in filter:
                filter['label'] = filter['label'].lower()
            if 'state' in filter:
                filter['state'] = filter['state'].capitalize()
        super().prepare_config(config)
        return config

    def on_task_input(self, task, config):
        """Generates and returns a list of entries from the deluge daemon."""
        config = self.prepare_config(config)
        # Reset the entries list
        client = self.setup_client(config)

        try:
            client.connect()
        except ConnectionError as exc:
            raise plugin.PluginError(
                f'Error connecting to deluge daemon: {exc}', logger=logger
            ) from exc

        entries = self.generate_entries(client, config)
        client.disconnect()
        return entries

    def generate_entries(self, client, config):
        entries = []
        filter = config.get('filter', {})
        torrents = client.call('core.get_torrents_status', filter or {}, [])
        for hash, torrent_dict in torrents.items():
            # Make sure it has a url so no plugins crash
            entry = Entry(deluge_id=hash, url='')
            config_path = os.path.expanduser(config.get('config_path', ''))
            if config_path:
                torrent_path = os.path.join(config_path, 'state', hash + '.torrent')
                if os.path.isfile(torrent_path):
                    entry['location'] = torrent_path
                    if not torrent_path.startswith('/'):
                        torrent_path = '/' + torrent_path
                    entry['url'] = 'file://' + torrent_path
                else:
                    logger.warning('Did not find torrent file at {}', torrent_path)
            for key, value in torrent_dict.items():
                # All fields provided by deluge get placed under the deluge_ namespace
                entry['deluge_' + key] = value
                # Some fields also get special handling
                if key in self.settings_map:
                    flexget_key = self.settings_map[key]
                    if isinstance(flexget_key, tuple):
                        flexget_key, format_func = flexget_key
                        value = format_func(value)
                    entry[flexget_key] = value
            entries.append(entry)

        return entries


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
                    'config_path': {'type': 'string', 'format': 'path'},
                    'action': {
                        'type': 'string',
                        'enum': ['add', 'remove', 'purge', 'pause', 'resume'],
                    },
                    'path': {'type': 'string'},
                    'move_completed_path': {'type': 'string'},
                    'label': {'type': 'string'},
                    'queue_to_top': {'type': 'boolean'},
                    'auto_managed': {'type': 'boolean'},
                    'max_up_speed': {'type': 'number'},
                    'max_down_speed': {'type': 'number'},
                    'max_connections': {'type': 'integer'},
                    'max_up_slots': {'type': 'integer'},
                    'ratio': {'type': 'number'},
                    'remove_at_ratio': {'type': 'boolean'},
                    'add_paused': {'type': 'boolean'},
                    'compact': {'type': 'boolean'},
                    'content_filename': {'type': 'string'},
                    'main_file_only': {'type': 'boolean'},
                    'main_file_ratio': {'type': 'number'},
                    'magnetization_timeout': {'type': 'integer'},
                    'keep_subs': {'type': 'boolean'},
                    'hide_sparse_files': {'type': 'boolean'},
                    'enabled': {'type': 'boolean'},
                    'container_directory': {'type': 'string'},
                },
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        super().prepare_config(config)
        config.setdefault('enabled', True)
        config.setdefault('action', 'add')
        config.setdefault('path', '')
        config.setdefault('move_completed_path', '')
        config.setdefault('label', '')
        config.setdefault('main_file_ratio', 0.90)
        config.setdefault('magnetization_timeout', 0)
        config.setdefault(
            'keep_subs', True
        )  # does nothing without 'content_filename' or 'main_file_only' enabled
        config.setdefault(
            'hide_sparse_files', False
        )  # does nothing without 'main_file_only' enabled
        return config

    def __init__(self):
        self.deluge_version = None
        self.options = {
            'max_up_speed': 'max_upload_speed',
            'max_down_speed': 'max_download_speed',
            'max_connections': 'max_connections',
            'max_up_slots': 'max_upload_slots',
            'auto_managed': 'auto_managed',
            'ratio': 'stop_ratio',
            'remove_at_ratio': 'remove_at_ratio',
            'add_paused': 'add_paused',
            'compact': 'compact_allocation',
        }

    @plugin.priority(120)
    def on_task_download(self, task, config):
        """
        Call download plugin to generate the temp files we will load into deluge
        then verify they are valid torrents
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get('download', self)
            for entry in task.accepted:
                if entry.get('deluge_id'):
                    # The torrent is already loaded in deluge, we don't need to get anything
                    continue
                if config['action'] != 'add' and entry.get('torrent_info_hash'):
                    # If we aren't adding the torrent new, all we need is info hash
                    continue
                download.get_temp_file(task, entry, handle_magnets=True)

    @plugin.priority(135)
    def on_task_output(self, task, config):
        """Add torrents to deluge at exit."""
        config = self.prepare_config(config)
        client = self.setup_client(config)
        # don't add when learning
        if task.options.learn:
            return
        if not config['enabled'] or not (task.accepted or task.options.test):
            return

        try:
            client.connect()
        except ConnectionError as exc:
            raise plugin.PluginError(
                f'Error connecting to deluge daemon: {exc}', logger=logger
            ) from exc

        if task.options.test:
            logger.debug('Test connection to deluge daemon successful.')
            client.disconnect()
            return

        # loop through entries to get a list of labels to add
        labels = set()
        for entry in task.accepted:
            label = entry.get('label') or config.get('label')
            if label and label.lower() != 'no label':
                try:
                    label = self._format_label(entry.render(label))
                    logger.debug('Rendered label: {}', label)
                except RenderError as e:
                    logger.error('Error rendering label `{}`: {}', label, e)
                    continue
                labels.add(label)
        if labels:
            # Make sure the label plugin is available and enabled, then add appropriate labels

            enabled_plugins = client.call('core.get_enabled_plugins')
            label_enabled = 'Label' in enabled_plugins
            if not label_enabled:
                available_plugins = client.call('core.get_available_plugins')
                if 'Label' in available_plugins:
                    logger.debug('Enabling label plugin in deluge')
                    label_enabled = client.call('core.enable_plugin', 'Label')
                else:
                    logger.error('Label plugin is not installed in deluge')

            if label_enabled:
                d_labels = client.call('label.get_labels')
                for label in labels:
                    if label not in d_labels:
                        logger.debug('Adding the label `{}` to deluge', label)
                        client.call('label.add', label)

        # add the torrents
        torrent_ids = client.call('core.get_session_state')
        for entry in task.accepted:
            # Generate deluge options dict for torrent add
            add_opts = {}
            try:
                path = entry.render(entry.get('path') or config['path'])
                if path:
                    add_opts['download_location'] = pathscrub(os.path.expanduser(path))
            except RenderError as e:
                logger.error('Could not set path for {}: {}', entry['title'], e)
            for fopt, dopt in self.options.items():
                value = entry.get(fopt, config.get(fopt))
                if value is not None:
                    add_opts[dopt] = value
                    if fopt == 'ratio':
                        add_opts['stop_at_ratio'] = True
            # Make another set of options, that get set after the torrent has been added
            modify_opts = {
                'queue_to_top': entry.get('queue_to_top', config.get('queue_to_top')),
                'main_file_only': entry.get('main_file_only', config.get('main_file_only', False)),
                'main_file_ratio': entry.get('main_file_ratio', config.get('main_file_ratio')),
                'hide_sparse_files': entry.get(
                    'hide_sparse_files', config.get('hide_sparse_files', True)
                ),
                'keep_subs': entry.get('keep_subs', config.get('keep_subs', True)),
                'container_directory': config.get('container_directory', ''),
            }
            try:
                label = entry.render(entry.get('label') or config['label'])
                modify_opts['label'] = self._format_label(label)
            except RenderError as e:
                logger.error('Error setting label for `{}`: {}', entry['title'], e)
            try:
                move_completed_path = entry.render(
                    entry.get('move_completed_path') or config['move_completed_path']
                )
                modify_opts['move_completed_path'] = pathscrub(
                    os.path.expanduser(move_completed_path)
                )
            except RenderError as e:
                logger.error('Error setting move_completed_path for {}: {}', entry['title'], e)
            try:
                content_filename = entry.get('content_filename') or config.get(
                    'content_filename', ''
                )
                modify_opts['content_filename'] = pathscrub(entry.render(content_filename))
            except RenderError as e:
                logger.error('Error setting content_filename for {}: {}', entry['title'], e)

            torrent_id = entry.get('deluge_id') or entry.get('torrent_info_hash')
            torrent_id = torrent_id and torrent_id.lower()
            if torrent_id in torrent_ids:
                logger.info('{} is already loaded in deluge, setting options', entry['title'])
                # Entry has a deluge id, verify the torrent is still in the deluge session and apply options
                # Since this is already loaded in deluge, we may also need to change the path
                modify_opts['path'] = add_opts.pop('download_location', None)
                client.call('core.set_torrent_options', [torrent_id], add_opts)
                self._set_torrent_options(client, torrent_id, entry, modify_opts)
            elif config['action'] != 'add':
                logger.warning(
                    'Cannot {} {}, because it is not loaded in deluge.',
                    config['action'],
                    entry['title'],
                )
                continue
            else:
                magnet, filedump = None, None
                if entry.get('url', '').startswith('magnet:'):
                    magnet = entry['url']
                else:
                    if not os.path.exists(entry['file']):
                        entry.fail('Downloaded temp file \'%s\' doesn\'t exist!' % entry['file'])
                        del entry['file']
                        return
                    with open(entry['file'], 'rb') as f:
                        filedump = base64.encodebytes(f.read())

                logger.verbose('Adding {} to deluge.', entry['title'])
                added_torrent = None
                if magnet:
                    try:
                        added_torrent = client.call('core.add_torrent_magnet', magnet, add_opts)
                    except Exception as exc:
                        logger.error('{} was not added to deluge! {}', entry['title'], exc)
                        logger.opt(exception=True).debug('Error adding magnet:')
                        entry.fail('Could not be added to deluge')
                    else:
                        if config.get('magnetization_timeout'):
                            timeout = config['magnetization_timeout']
                            logger.verbose(
                                'Waiting {} seconds for "{}" to magnetize', timeout, entry['title']
                            )
                            for _ in range(timeout):
                                time.sleep(1)
                                try:
                                    status = client.call(
                                        'core.get_torrent_status', added_torrent, ['files']
                                    )
                                except Exception as err:
                                    logger.error('wait_for_metadata Error: {}', err)
                                    break
                                if status.get('files'):
                                    logger.info('"{}" magnetization successful', entry['title'])
                                    break
                            else:
                                logger.warning(
                                    '"{}" did not magnetize before the timeout elapsed, '
                                    'file list unavailable for processing.',
                                    entry['title'],
                                )
                else:
                    try:
                        added_torrent = client.call(
                            'core.add_torrent_file', entry['title'], filedump, add_opts
                        )
                    except Exception as e:
                        logger.error('{} was not added to deluge! {}', entry['title'], e)
                        entry.fail('Could not be added to deluge')
                if not added_torrent:
                    logger.error('There was an error adding {} to deluge.', entry['title'])
                else:
                    logger.info('{} successfully added to deluge.', entry['title'])
                    self._set_torrent_options(client, added_torrent, entry, modify_opts)
            if config['action'] in ('remove', 'purge'):
                client.call('core.remove_torrent', torrent_id, config['action'] == 'purge')
                logger.info('{} removed from deluge.', entry['title'])
            elif config['action'] == 'pause':
                client.call('core.pause_torrent', [torrent_id])
                logger.info('{} has been paused in deluge.', entry['title'])
            elif config['action'] == 'resume':
                client.call('core.resume_torrent', [torrent_id])
                logger.info('{} has been resumed in deluge.', entry['title'])

        client.disconnect()

    def on_task_learn(self, task, config):
        """ Make sure all temp files are cleaned up when entries are learned """
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get('download', self)
            download.cleanup_temp_files(task)

    def on_task_abort(self, task, config):
        """Make sure normal cleanup tasks still happen on abort."""
        self.on_task_learn(task, config)

    def _format_label(self, label):
        """Makes a string compliant with deluge label naming rules"""
        # "No Label" is a special identifier to unset a label
        if label.lower() == 'no label':
            return 'No Label'
        return re.sub(r'[^\w-]+', '_', label.lower())

    def _set_torrent_options(self, client, torrent_id, entry, opts):
        """Gets called when a torrent was added to the daemon."""
        entry['deluge_id'] = torrent_id

        if opts.get('move_completed_path'):
            client.call(
                'core.set_torrent_options',
                [torrent_id],
                {'move_completed': True, 'move_completed_path': opts['move_completed_path']},
            )
            logger.debug(
                '{} move on complete set to {}', entry['title'], opts['move_completed_path']
            )
        if opts.get('label'):
            client.call('label.set_torrent', torrent_id, opts['label'])
        if opts.get('queue_to_top') is not None:
            if opts['queue_to_top']:
                client.call('core.queue_top', [torrent_id])
                logger.debug('{} moved to top of queue', entry['title'])
            else:
                client.call('core.queue_bottom', [torrent_id])
                logger.debug('{} moved to bottom of queue', entry['title'])

        status_keys = [
            'files',
            'total_size',
            'save_path',
            'move_on_completed_path',
            'move_on_completed',
            'progress',
        ]
        status = client.call('core.get_torrent_status', torrent_id, status_keys)
        # Determine where the file should be
        move_now_path = None
        if opts.get('move_completed_path'):
            if status['progress'] == 100:
                move_now_path = opts['move_completed_path']
            else:
                # Deluge will unset the move completed option if we move the storage, forgo setting proper
                # path, in favor of leaving proper final location.
                logger.debug(
                    'Not moving storage for {}, as this will prevent move_completed_path.',
                    entry['title'],
                )
        elif opts.get('path'):
            move_now_path = opts['path']

        if move_now_path and os.path.normpath(move_now_path) != os.path.normpath(
            status['save_path']
        ):
            logger.debug('Moving storage for {} to {}', entry['title'], move_now_path)
            client.call('core.move_storage', [torrent_id], move_now_path)

        big_file_name = ''
        if opts.get('content_filename') or opts.get('main_file_only'):
            # find a file that makes up more than main_file_ratio (default: 90%) of the total size
            main_file = None
            for file in status['files']:
                if file['size'] > (status['total_size'] * opts.get('main_file_ratio')):
                    main_file = file
                    break

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
                if client.host in ['127.0.0.1', 'localhost']:
                    counter = 2
                    while file_exists(name):
                        name = ''.join(
                            [
                                os.path.splitext(name)[0],
                                " (",
                                str(counter),
                                ')',
                                os.path.splitext(name)[1],
                            ]
                        )
                        counter += 1
                else:
                    logger.debug(
                        'Cannot ensure content_filename is unique when adding to a remote deluge daemon.'
                    )
                return name

            def rename(file, new_name):
                # Renames a file in torrent
                client.call('core.rename_files', torrent_id, [(file['index'], new_name)])
                logger.debug('File {} in {} renamed to {}', file['path'], entry['title'], new_name)

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
                top_files_dir = "/"
                if os.path.dirname(main_file['path']) not in ("", "/"):
                    # check for top folder in user config
                    if (
                        opts.get('content_filename')
                        and os.path.dirname(opts['content_filename']) != ""
                    ):
                        top_files_dir = os.path.dirname(opts['content_filename']) + "/"
                    else:
                        top_files_dir = os.path.dirname(main_file['path']) + "/"

                if opts.get('content_filename'):
                    # rename the main file
                    big_file_name = (
                        top_files_dir
                        + os.path.basename(opts['content_filename'])
                        + os.path.splitext(main_file['path'])[1]
                    )
                    big_file_name = unused_name(big_file_name)
                    rename(main_file, big_file_name)

                    # rename subs along with the main file
                    if sub_file is not None and keep_subs:
                        sub_file_name = (
                            os.path.splitext(big_file_name)[0]
                            + os.path.splitext(sub_file['path'])[1]
                        )
                        rename(sub_file, sub_file_name)

                if opts.get('main_file_only'):
                    # download only the main file (and subs)
                    file_priorities = [
                        1 if f == main_file or f == sub_file and keep_subs else 0
                        for f in status['files']
                    ]
                    client.call(
                        'core.set_torrent_options',
                        [torrent_id],
                        {'file_priorities': file_priorities},
                    )

                    if opts.get('hide_sparse_files'):
                        # hide the other sparse files that are not supposed to download but are created anyway
                        # http://dev.deluge-torrent.org/ticket/1827
                        # Made sparse files behave better with deluge http://flexget.com/ticket/2881
                        sparse_files = [
                            f
                            for f in status['files']
                            if f != main_file and (f != sub_file or not keep_subs)
                        ]
                        rename_pairs = [
                            (
                                f['index'],
                                top_files_dir + ".sparse_files/" + os.path.basename(f['path']),
                            )
                            for f in sparse_files
                        ]
                        client.call('core.rename_files', torrent_id, rename_pairs)
            else:
                logger.warning(
                    'No files in "{}" are > {:.0f}% of content size, no files renamed.',
                    entry['title'],
                    opts.get('main_file_ratio') * 100,
                )

        container_directory = pathscrub(
            entry.render(entry.get('container_directory') or opts.get('container_directory', ''))
        )
        if container_directory:
            if big_file_name:
                folder_structure = big_file_name.split(os.sep)
            elif len(status['files']) > 0:
                folder_structure = status['files'][0]['path'].split(os.sep)
            else:
                folder_structure = []
            if len(folder_structure) > 1:
                logger.verbose(
                    'Renaming Folder {} to {}', folder_structure[0], container_directory
                )
                client.call(
                    'core.rename_folder', torrent_id, folder_structure[0], container_directory
                )
            else:
                logger.debug(
                    'container_directory specified however the torrent {} does not have a directory structure; skipping folder rename',
                    entry['title'],
                )


@event('plugin.register')
def register_plugin():
    plugin.register(InputDeluge, 'from_deluge', api_ver=2)
    plugin.register(OutputDeluge, 'deluge', api_ver=2)
