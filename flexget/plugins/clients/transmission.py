import os
import pathlib
import re
from datetime import datetime, timedelta
from fnmatch import fnmatch
from functools import partial
from netrc import NetrcParseError, netrc
from time import sleep
from typing import TYPE_CHECKING
from urllib.parse import urlparse

try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata  # TODO: remove this after we drop python 3.7

import packaging.specifiers
import packaging.version
from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError
from flexget.utils.tools import parse_timedelta

try:
    import transmission_rpc
    from transmission_rpc.error import (
        TransmissionAuthError,
        TransmissionConnectError,
        TransmissionError,
        TransmissionTimeoutError,
    )
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    transmission_rpc = None
    TransmissionError = None
    TransmissionAuthError = None
    TransmissionConnectError = None
    TransmissionTimeoutError = None

if TYPE_CHECKING:
    from transmission_rpc import Torrent

logger = logger.bind(name='transmission')

__version__ = '>=4.1.4,<5.0.0'
__package__ = 'transmission-rpc'
__requirement__ = packaging.specifiers.SpecifierSet(__version__)


class TransmissionBase:
    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 9091)
        config.setdefault('main_file_ratio', 0.9)
        if 'netrc' in config:
            netrc_path = os.path.expanduser(config['netrc'])
            try:
                config['username'], _, config['password'] = netrc(netrc_path).authenticators(
                    config['host']
                )
            except OSError as e:
                logger.error('netrc: unable to open: {}', e.filename)
            except NetrcParseError as e:
                logger.error('netrc: {}, file: {}, line: {}', e.msg, e.filename, e.lineno)
        return config

    def create_rpc_client(self, config) -> 'transmission_rpc.Client':
        user, password = config.get('username'), config.get('password')
        urlo = urlparse(config['host'])

        if urlo.scheme == '':
            urlo = urlparse('http://' + config['host'])

        protocol = urlo.scheme if urlo.scheme else 'http'
        port = str(urlo.port) if urlo.port else config['port']
        path = urlo.path.rstrip('rpc') if urlo.path else '/transmission/'

        logger.debug('Connecting to {}://{}:{}{}', protocol, urlo.hostname, port, path)

        try:
            cli = transmission_rpc.Client(
                protocol=protocol,
                host=urlo.hostname,
                port=port,
                path=path,
                username=user,
                password=password,
                timeout=30,
            )
        except TransmissionAuthError:
            raise plugin.PluginError(
                "Username/password for transmission is incorrect. Cannot connect."
            )
        except TransmissionTimeoutError:
            raise plugin.PluginError("Cannot connect to transmission: Connection timed out.")
        except TransmissionConnectError as e:
            raise plugin.PluginError("Error connecting to transmission: %s" % e.args[0].reason)
        except TransmissionError:
            raise plugin.PluginError("Error connecting to transmission")
        return cli

    def torrent_info(self, torrent: 'Torrent', config):
        done = torrent.total_size > 0
        vloc = None
        best = None
        for _, tf in enumerate(torrent.get_files()):
            if tf.selected:
                if tf.size <= 0 or tf.completed < tf.size:
                    done = False
                    break
                if not best or tf.size > best[1]:
                    best = (tf.name, tf.size)
        if (
            done
            and best
            and (100 * float(best[1]) / float(torrent.total_size))
            >= (config['main_file_ratio'] * 100)
        ):
            vloc = (f'{torrent.download_dir}/{best[0]}').replace('/', os.sep)
        return done, vloc

    def check_seed_limits(self, torrent: 'Torrent', session):
        seed_limit_ok = True  # will remain if no seed ratio defined
        idle_limit_ok = True  # will remain if no idle limit defined

        if torrent.get('seedRatioMode') == 1:  # use torrent's own seed ratio limit
            seed_limit_ok = torrent.upload_ratio >= torrent.seed_ratio_limit
        elif torrent.get('seedRatioMode') == 0:  # use global rules
            if session.seedRatioLimited:
                seed_limit_ok = torrent.upload_ratio >= session.seedRatioLimit

        if torrent.get('seedIdleMode') == 1:  # use torrent's own idle limit
            idle_limit_ok = (
                torrent.activity_date + timedelta(minutes=torrent.seed_idle_limit)
                < datetime.now().astimezone()
            )
        elif torrent.get('seedIdleMode') == 0:  # use global rules
            if session.idle_seeding_limit_enabled:
                idle_limit_ok = (
                    torrent.activity_date + timedelta(minutes=session.idle_seeding_limit)
                    < datetime.now().astimezone()
                )

        return seed_limit_ok, idle_limit_ok

    def on_task_start(self, task, config):
        if transmission_rpc is None:
            raise plugin.PluginError(
                f'{__package__} module version {__version__} required.', logger
            )

        v = importlib_metadata.version(__package__)
        if not __requirement__.contains(v):
            raise plugin.PluginError(
                f'{__package__} module version mismatch, requiring {__package__}{__version__}',
                logger,
            )

        # Mark rpc client for garbage collector so every task can start
        # a fresh new according its own config - fix to bug #2804
        config = self.prepare_config(config)
        if config['enabled']:
            if task.options.test:
                logger.info('Trying to connect to transmission...')
                client = self.create_rpc_client(config)
                if client:
                    logger.info('Successfully connected to transmission.')
                else:
                    logger.error('It looks like there was a problem connecting to transmission.')


class PluginTransmissionInput(TransmissionBase):
    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'netrc': {'type': 'string', 'format': 'file'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'enabled': {'type': 'boolean'},
                    'only_complete': {'type': 'boolean'},
                },
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        config = TransmissionBase.prepare_config(self, config)
        config.setdefault('only_complete', False)
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        client = self.create_rpc_client(config)
        entries = []

        session = client.get_session()

        for torrent in client.get_torrents():
            seed_ratio_ok, idle_limit_ok = self.check_seed_limits(torrent, session)
            if config['only_complete'] and not (
                seed_ratio_ok and idle_limit_ok and torrent.progress == 100
            ):
                continue
            entry = Entry(
                title=torrent.name,
                url='',
                torrent_info_hash=torrent.hashString,
                content_size=torrent.total_size / (1024 * 1024),
            )
            # Location of torrent is only valid if transmission is on same machine as flexget
            if config['host'] in ('localhost', '127.0.0.1'):
                entry['location'] = torrent.torrent_file
                entry['url'] = pathlib.Path(torrent.torrent_file).as_uri()
            for attr, field in {
                'id': 'id',
                'activityDate': 'activity_date',
                'comment': 'comment',
                'desiredAvailable': 'desired_available',
                'downloadDir': 'download_dir',
                'isFinished': 'is_finished',
                'isPrivate': 'is_private',
                'isStalled': 'is_stalled',
                'leftUntilDone': 'left_until_done',
                'ratio': 'ratio',
                'status': 'status',
                'date_active': 'date_active',
                'date_added': 'date_added',
                'date_done': 'date_done',
                'date_started': 'date_started',
                'errorString': 'error_string',
                'priority': 'priority',
                'progress': 'progress',
                'secondsDownloading': 'seconds_downloading',
                'secondsSeeding': 'seconds_seeding',
                'torrentFile': 'torrent_file',
                'labels': 'labels',
            }.items():
                try:
                    value = getattr(torrent, field)
                except Exception:
                    logger.opt(exception=True).debug(
                        'error when requesting transmissionrpc attribute {}', attr
                    )
                else:
                    # transmission-rpc adds timezone info to datetimes,
                    # which makes them hard to deal with. Strip it.
                    if isinstance(value, datetime):
                        value = value.replace(tzinfo=None)
                    entry['transmission_' + attr] = value
            # Availability in percent
            entry['transmission_availability'] = (
                (torrent.desired_available / torrent.left_until_done)
                if torrent.left_until_done
                else 0
            )

            entry['transmission_trackers'] = [t.announce for t in torrent.trackers]
            entry['transmission_seed_ratio_ok'] = seed_ratio_ok
            entry['transmission_idle_limit_ok'] = idle_limit_ok
            st_error_to_desc = {
                0: 'OK',
                1: 'tracker_warning',
                2: 'tracker_error',
                3: 'local_error',
            }
            entry['transmission_error_state'] = st_error_to_desc[torrent.error]
            # Built in done_date doesn't work when user adds an already completed file to transmission
            if torrent.progress == 100:
                date_done = torrent.done_date or torrent.added_date
                if date_done:
                    date_done = date_done.replace(tzinfo=None)
                entry['transmission_date_done'] = date_done

            entries.append(entry)
        return entries


class PluginTransmission(TransmissionBase):
    """
    Add url from entry url to transmission

    Example::

      transmission:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location

    Default values for the config elements::

      transmission:
        host: localhost
        port: 9091
        enabled: yes
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'netrc': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'action': {
                        'type': 'string',
                        'enum': ['add', 'remove', 'purge', 'pause', 'resume', 'bypass_queue'],
                    },
                    'path': {'type': 'string'},
                    'max_up_speed': {'type': 'number'},
                    'max_down_speed': {'type': 'number'},
                    'max_connections': {'type': 'integer'},
                    'ratio': {'type': 'number'},
                    'add_paused': {'type': 'boolean'},
                    'content_filename': {'type': 'string'},
                    'main_file_only': {'type': 'boolean'},
                    'main_file_ratio': {'type': 'number'},
                    'magnetization_timeout': {'type': 'integer'},
                    'enabled': {'type': 'boolean'},
                    'include_subs': {'type': 'boolean'},
                    'bandwidth_priority': {'type': 'number'},
                    'honor_limits': {'type': 'boolean'},
                    'include_files': one_or_more({'type': 'string'}),
                    'skip_files': one_or_more({'type': 'string'}),
                    'rename_like_files': {'type': 'boolean'},
                    'queue_position': {'type': 'integer'},
                    'labels': {'type': 'array', 'items': {'type': 'string'}},
                },
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        config = TransmissionBase.prepare_config(self, config)
        config.setdefault('action', 'add')
        config.setdefault('path', '')
        config.setdefault('main_file_only', False)
        config.setdefault('magnetization_timeout', 0)
        config.setdefault('include_subs', False)
        config.setdefault('rename_like_files', False)
        config.setdefault('include_files', [])
        return config

    @plugin.priority(120)
    def on_task_download(self, task, config):
        """
        Call download plugin to generate the temp files we will load
        into deluge then verify they are valid torrents
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get('download', self)
            for entry in task.accepted:
                if entry.get('transmission_id'):
                    # The torrent is already loaded in deluge, we don't need to get anything
                    continue
                if config['action'] != 'add' and entry.get('torrent_info_hash'):
                    # If we aren't adding the torrent new, all we need is info hash
                    continue
                download.get_temp_file(task, entry, handle_magnets=True, fail_html=True)

    @plugin.priority(135)
    def on_task_output(self, task, config):
        config = self.prepare_config(config)
        # don't add when learning
        if task.options.learn:
            return
        if not config['enabled']:
            return
        # Do not run if there is nothing to do
        if not task.accepted:
            return
        client = self.create_rpc_client(config)
        if client:
            logger.debug('Successfully connected to transmission.')
        else:
            raise plugin.PluginError("Couldn't connect to transmission.")
        session_torrents = client.get_torrents()
        for entry in task.accepted:
            if task.options.test:
                logger.info('Would {} {} in transmission.', config['action'], entry['title'])
                continue
            # Compile user options into appropriate dict
            options = self._make_torrent_options_dict(config, entry)
            torrent_info = None
            for t in session_torrents:
                if t.hashString.lower() == entry.get(
                    'torrent_info_hash', ''
                ).lower() or t.id == entry.get('transmission_id'):
                    torrent_info = t
                    logger.debug(
                        'Found {} already loaded in transmission as {}',
                        entry['title'],
                        torrent_info.name,
                    )
                    break

            if not torrent_info:
                if config['action'] != 'add':
                    logger.warning(
                        'Cannot {} {} because it is not loaded in transmission.',
                        config['action'],
                        entry['title'],
                    )
                    continue
                downloaded = not entry['url'].startswith('magnet:')

                # Check that file is downloaded
                if downloaded and 'file' not in entry:
                    entry.fail('`file` field missing?')
                    continue

                # Verify the temp file exists
                if downloaded and not os.path.exists(entry['file']):
                    tmp_path = os.path.join(task.manager.config_base, 'temp')
                    logger.debug('entry: {}', entry)
                    logger.debug('temp: {}', ', '.join(os.listdir(tmp_path)))
                    entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                    continue

                try:
                    if downloaded:
                        with open(entry['file'], 'rb') as f:
                            torrent_info = client.add_torrent(f, 30, **options['add'])
                    else:
                        if options['post'].get('magnetization_timeout', 0) > 0:
                            options['add']['paused'] = False
                        torrent_info = client.add_torrent(entry['url'], **options['add'])
                except TransmissionError as e:
                    logger.opt(exception=True).debug('TransmissionError')
                    logger.debug('Failed options dict: {}', options['add'])
                    msg = 'Error adding {} to transmission. TransmissionError: {}'.format(
                        entry['title'], e.message or 'N/A'
                    )
                    logger.error(msg)
                    entry.fail(msg)
                    continue
                logger.info('"{}" torrent added to transmission', entry['title'])
                # The info returned by the add call is incomplete, refresh it
                torrent_info = client.get_torrent(torrent_info.id)
            else:
                # Torrent already loaded in transmission
                if options['add'].get('download_dir'):
                    logger.log(
                        "VERBOSE",
                        'Moving {} to "{}"',
                        torrent_info.name,
                        options['add']['download_dir'],
                    )
                    # Move data even if current reported torrent location matches new location
                    # as transmission may fail to automatically move completed file to final
                    # location but continue reporting final location instead of real location.
                    # In such case this will kick transmission to really move data.
                    # If data is already located at new location then transmission just ignore
                    # this command.
                    client.move_torrent_data(
                        torrent_info.hashString, options['add']['download_dir'], 120
                    )

            try:
                total_size = torrent_info.total_size
                main_id = None
                find_main_file = (
                    options['post'].get('main_file_only') or 'content_filename' in options['post']
                )
                skip_files = options['post'].get('skip_files')
                # We need to index the files if any of the following are defined
                if find_main_file or skip_files:
                    file_list = torrent_info.get_files()

                    if options['post'].get('magnetization_timeout', 0) > 0 and not file_list:
                        logger.debug(
                            'Waiting {} seconds for "{}" to magnetize',
                            options['post']['magnetization_timeout'],
                            entry['title'],
                        )
                        for _ in range(options['post']['magnetization_timeout']):
                            sleep(1)
                            file_list = torrent_info.get_files()
                            if file_list:
                                total_size = client.get_torrent(
                                    torrent_info.id, ['id', 'totalSize']
                                ).total_size
                                break
                        else:
                            logger.warning(
                                '"{}" did not magnetize before the timeout elapsed, file list unavailable for processing.',
                                entry['title'],
                            )

                    # Find files based on config
                    dl_list = []
                    skip_list = []
                    main_list = []
                    ext_list = ['*.srt', '*.sub', '*.idx', '*.ssa', '*.ass']

                    main_ratio = config['main_file_ratio']
                    if 'main_file_ratio' in options['post']:
                        main_ratio = options['post']['main_file_ratio']

                    for file_id, file in enumerate(file_list):
                        # No need to set main_id if we're not going to need it
                        if find_main_file and file.size > total_size * main_ratio:
                            main_id = file_id

                        if 'include_files' in options['post']:
                            if any(
                                fnmatch(file.name, mask)
                                for mask in options['post']['include_files']
                            ):
                                dl_list.append(file_id)
                            elif options['post'].get('include_subs') and any(
                                fnmatch(file.name, mask) for mask in ext_list
                            ):
                                dl_list.append(file_id)

                        if skip_files:
                            if any(fnmatch(file.name, mask) for mask in skip_files):
                                skip_list.append(file_id)

                    if main_id is not None:
                        # Look for files matching main ID title but with a different extension
                        if options['post'].get('rename_like_files'):
                            for file_id, file in enumerate(file_list):
                                # if this filename matches main filename we want to rename it as well
                                fs = os.path.splitext(file.name)
                                if fs[0] == os.path.splitext(file_list[main_id].name)[0]:
                                    main_list.append(file_id)
                        else:
                            main_list = [main_id]

                        if main_id not in dl_list:
                            dl_list.append(main_id)
                    elif find_main_file:
                        logger.warning(
                            'No files in "{}" are > {:.0f}% of content size, no files renamed.',
                            entry['title'],
                            main_ratio * 100,
                        )

                    # If we have a main file and want to rename it and associated files
                    if 'content_filename' in options['post'] and main_id is not None:
                        if 'download_dir' not in options['add']:
                            download_dir = client.get_session().download_dir
                        else:
                            download_dir = options['add']['download_dir']

                        # Get new filename without ext
                        file_ext = os.path.splitext(file_list[main_id].name)[1]
                        file_path = os.path.dirname(
                            os.path.join(download_dir, file_list[main_id].name)
                        )
                        filename = options['post']['content_filename']
                        if config['host'] == 'localhost' or config['host'] == '127.0.0.1':
                            counter = 1
                            while os.path.exists(os.path.join(file_path, filename + file_ext)):
                                # Try appending a (#) suffix till a unique filename is found
                                filename = f'{options["post"]["content_filename"]}({counter})'
                                counter += 1
                        else:
                            logger.debug(
                                'Cannot ensure content_filename is unique '
                                'when adding to a remote transmission daemon.'
                            )

                        for file_id in main_list:
                            file_ext = os.path.splitext(file_list[file_id].name)[1]
                            logger.debug(
                                'File {} renamed to {}',
                                file_list[file_id].name,
                                filename + file_ext,
                            )
                            # change to below when set_files will allow setting name, more efficient to have one call
                            # fl[index]['name'] = os.path.basename(pathscrub(filename + file_ext).encode('utf-8'))
                            try:
                                client.rename_torrent_path(
                                    torrent_info.id,
                                    file_list[file_id].name,
                                    os.path.basename(str(pathscrub(filename + file_ext))),
                                )
                            except TransmissionError:
                                logger.error(
                                    'content_filename only supported with transmission 2.8+'
                                )

                    if options['post'].get('main_file_only') and main_id is not None:
                        # Set Unwanted Files
                        options['change']['files_unwanted'] = [
                            x for x in range(len(file_list)) if x not in dl_list
                        ]
                        options['change']['files_wanted'] = dl_list
                        logger.debug(
                            'Downloading {} of {} files in torrent.',
                            len(options['change']['files_wanted']),
                            len(file_list),
                        )
                    elif (
                        not options['post'].get('main_file_only') or main_id is None
                    ) and skip_files:
                        # If no main file and we want to skip files

                        if len(skip_list) >= len(file_list):
                            logger.debug(
                                'skip_files filter would cause no files to be downloaded; '
                                'including all files in torrent.'
                            )
                        else:
                            options['change']['files_unwanted'] = skip_list
                            options['change']['files_wanted'] = [
                                x for x in range(len(file_list)) if x not in skip_list
                            ]
                            logger.debug(
                                'Downloading {} of {} files in torrent.',
                                len(options['change']['files_wanted']),
                                len(file_list),
                            )

                # Set any changed file properties
                if list(options['change'].keys()):
                    client.change_torrent(torrent_info.id, **options['change'])

                start_torrent = partial(client.start_torrent, [torrent_info.id])

                if config['action'] == 'add':
                    # if add_paused was defined and set to False start the torrent;
                    # prevents downloading data before we set what files we want
                    start_paused = (
                        options['post']['paused']
                        if 'paused' in options['post']
                        else not client.get_session().start_added_torrents
                    )
                    if start_paused:
                        client.stop_torrent(torrent_info.id)
                    else:
                        client.start_torrent(torrent_info.id)
                elif config['action'] in ('remove', 'purge'):
                    client.remove_torrent(
                        [torrent_info.id], delete_data=config['action'] == 'purge'
                    )
                    logger.info('{}d {} from transmission', config['action'], torrent_info.name)
                elif config['action'] == 'pause':
                    client.stop_torrent([torrent_info.id])
                    logger.info('paused {} in transmission', torrent_info.name)
                elif config['action'] == 'resume':
                    start_torrent()
                    logger.info('resumed {} in transmission', torrent_info.name)
                elif config['action'] == 'bypass_queue':
                    start_torrent(bypass_queue=True)
                    logger.info('resumed (bypass queue) {} in transmission', torrent_info.name)

            except TransmissionError as e:
                logger.opt(exception=True).debug('TransmissionError')
                logger.debug('Failed options dict: {}', options)
                msg = 'Error trying to {} {}, TransmissionError: {}'.format(
                    config['action'], entry['title'], e.message or 'N/A'
                )
                logger.error(msg)
                continue

    def _make_torrent_options_dict(self, config, entry):
        opt_dic = {}

        for opt_key in (
            'path',
            'add_paused',
            'honor_limits',
            'bandwidth_priority',
            'max_connections',
            'max_up_speed',
            'max_down_speed',
            'ratio',
            'main_file_only',
            'main_file_ratio',
            'magnetization_timeout',
            'include_subs',
            'content_filename',
            'include_files',
            'skip_files',
            'rename_like_files',
            'queue_position',
            'labels',
        ):
            # Values do not merge config with task
            # Task takes priority then config is used
            if opt_key in entry:
                opt_dic[opt_key] = entry[opt_key]
            elif opt_key in config:
                opt_dic[opt_key] = config[opt_key]

        options = {'add': {}, 'change': {}, 'post': {}}

        add = options['add']
        if opt_dic.get('path'):
            try:
                path = os.path.expanduser(entry.render(opt_dic['path']))
            except RenderError as e:
                logger.error('Error setting path for {}: {}', entry['title'], e)
            else:
                # Transmission doesn't like it when paths end in a separator
                path = path.rstrip('\\/')
                add['download_dir'] = pathscrub(path)
        # make sure we add it paused, will modify status after adding
        add['paused'] = True

        change = options['change']
        if 'bandwidth_priority' in opt_dic:
            change['bandwidthPriority'] = opt_dic['bandwidth_priority']
        if 'honor_limits' in opt_dic and not opt_dic['honor_limits']:
            change['honorsSessionLimits'] = False
        if 'max_up_speed' in opt_dic:
            change['uploadLimit'] = opt_dic['max_up_speed']
            change['uploadLimited'] = True
        if 'max_down_speed' in opt_dic:
            change['downloadLimit'] = opt_dic['max_down_speed']
            change['downloadLimited'] = True
        if 'max_connections' in opt_dic:
            change['peer_limit'] = opt_dic['max_connections']

        if 'ratio' in opt_dic:
            change['seedRatioLimit'] = opt_dic['ratio']
            if opt_dic['ratio'] == -1:
                # seedRatioMode:
                # 0 follow the global settings
                # 1 override the global settings, seeding until a certain ratio
                # 2 override the global settings, seeding regardless of ratio
                change['seedRatioMode'] = 2
            else:
                change['seedRatioMode'] = 1

        if 'queue_position' in opt_dic:
            change['queuePosition'] = opt_dic['queue_position']

        if 'labels' in opt_dic:
            change['labels'] = opt_dic['labels']

        post = options['post']
        # set to modify paused status after
        if 'add_paused' in opt_dic:
            post['paused'] = opt_dic['add_paused']
        if 'main_file_only' in opt_dic:
            post['main_file_only'] = opt_dic['main_file_only']
        if 'main_file_ratio' in opt_dic:
            post['main_file_ratio'] = opt_dic['main_file_ratio']
        if 'magnetization_timeout' in opt_dic:
            post['magnetization_timeout'] = opt_dic['magnetization_timeout']
        if 'include_subs' in opt_dic:
            post['include_subs'] = opt_dic['include_subs']
        if 'content_filename' in opt_dic:
            try:
                post['content_filename'] = entry.render(opt_dic['content_filename'])
            except RenderError as e:
                logger.error('Unable to render content_filename {}: {}', entry['title'], e)
        if 'skip_files' in opt_dic:
            post['skip_files'] = opt_dic['skip_files']
            if not isinstance(post['skip_files'], list):
                post['skip_files'] = [post['skip_files']]
        if 'include_files' in opt_dic:
            post['include_files'] = opt_dic['include_files']
            if not isinstance(post['include_files'], list):
                post['include_files'] = [post['include_files']]
        if 'rename_like_files' in opt_dic:
            post['rename_like_files'] = opt_dic['rename_like_files']
        return options

    def on_task_learn(self, task, config):
        """Make sure all temp files are cleaned up when entries are learned"""
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get('download', self)
            download.cleanup_temp_files(task)

    on_task_abort = on_task_learn


class PluginTransmissionClean(TransmissionBase):
    """
    DEPRECATED: A separate task using from_transmission and transmission with remove action should be used instead.

    Remove completed torrents from Transmission.

    Examples::

      clean_transmission: yes  # ignore both time and ratio

      clean_transmission:      # uses transmission's internal limits for idle time and seed ratio ( if defined )
        transmission_seed_limits: yes

      clean_transmission:      # matches time only
        finished_for: 2 hours

      clean_transmission:      # matches ratio only
        min_ratio: 0.5

      clean_transmission:      # matches time OR ratio
        finished_for: 2 hours
        min_ratio: 0.5

    Default values for the config elements::

      clean_transmission:
        host: localhost
        port: 9091
        enabled: yes
    """

    schema = {
        "deprecated": "The clean_transmission plugin is deprecated. Configure a new task using the from_transmission "
        "plugin as well as the transmission plugin using the remove or purge action.",
        "anyOf": [
            {"type": "boolean"},
            {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "netrc": {"type": "string", "format": "file"},
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "min_ratio": {"type": "number"},
                    "finished_for": {"type": "string", "format": "interval"},
                    "transmission_seed_limits": {"type": "boolean"},
                    "delete_files": {"type": "boolean"},
                    "tracker": {"type": "string", "format": "regex"},
                    "preserve_tracker": {"type": "string", "format": "regex"},
                    "directories": {
                        "type": "array",
                        "items": {"type": "string", "format": "regex"},
                    },
                },
                "additionalProperties": False,
            },
        ],
    }

    def on_task_exit(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled'] or task.options.learn:
            return
        client = self.create_rpc_client(config)
        tracker_re = re.compile(config['tracker'], re.IGNORECASE) if 'tracker' in config else None
        preserve_tracker_re = (
            re.compile(config['preserve_tracker'], re.IGNORECASE)
            if 'preserve_tracker' in config
            else None
        )

        session = client.get_session()

        remove_ids = []
        for torrent in client.get_torrents():
            logger.log(
                "VERBOSE",
                'Torrent "{}": status: "{}" - ratio: {} - date added: {}',
                torrent.name,
                torrent.status,
                torrent.ratio,
                torrent.added_date,
            )
            downloaded, dummy = self.torrent_info(torrent, config)
            if not downloaded:
                continue
            if config.get('transmission_seed_limits'):
                seed_ratio_ok, idle_limit_ok = self.check_seed_limits(torrent, session)
                if not seed_ratio_ok or not idle_limit_ok:
                    continue
            if 'min_ratio' in config:
                if torrent.ratio < config['min_ratio']:
                    continue
            if 'finished_for' in config:
                # done date might be invalid if this torrent was added to transmission when already completed
                started_seeding = max(torrent.added_date, torrent.done_date)
                if started_seeding + parse_timedelta(config['finished_for']) > datetime.now():
                    continue
            tracker_hosts = [urlparse(tracker.announce).hostname for tracker in torrent.trackers]
            if 'tracker' in config:
                if not any(tracker_re.search(tracker) for tracker in tracker_hosts):
                    continue
            if 'preserve_tracker' in config:
                if any(preserve_tracker_re.search(tracker) for tracker in tracker_hosts):
                    continue
            if config.get('directories'):
                if not any(
                    re.search(d, torrent.download_dir, re.IGNORECASE)
                    for d in config['directories']
                ):
                    continue
            if task.options.test:
                logger.info('Would remove finished torrent `{}` from transmission', torrent.name)
                continue
            logger.info('Removing finished torrent `{}` from transmission', torrent.name)
            remove_ids.append(torrent.id)
        if remove_ids:
            client.remove_torrent(remove_ids, config.get('delete_files'))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTransmission, 'transmission', api_ver=2)
    plugin.register(PluginTransmissionInput, 'from_transmission', api_ver=2)
    plugin.register(PluginTransmissionClean, 'clean_transmission', api_ver=2)
