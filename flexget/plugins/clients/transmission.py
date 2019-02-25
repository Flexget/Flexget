from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse
from future.utils import text_to_native_str

import os
import logging
import base64
import re
from datetime import datetime
from datetime import timedelta
from netrc import netrc, NetrcParseError
from time import sleep

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub
from flexget.utils.tools import parse_timedelta

from flexget.config_schema import one_or_more
from fnmatch import fnmatch

try:
    import transmissionrpc
    from transmissionrpc import TransmissionError
    from transmissionrpc import HTTPHandlerError
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    pass

log = logging.getLogger('transmission')


class TransmissionBase(object):
    def __init__(self):
        self.client = None
        self.opener = None

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
            except IOError as e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError as e:
                log.error('netrc: %s, file: %s, line: %s' % (e.msg, e.filename, e.lineno))
        return config

    def create_rpc_client(self, config):
        user, password = config.get('username'), config.get('password')

        try:
            cli = transmissionrpc.Client(config['host'], config['port'], user, password)
        except TransmissionError as e:
            if isinstance(e.original, HTTPHandlerError):
                if e.original.code == 111:
                    raise plugin.PluginError("Cannot connect to transmission. Is it running?")
                elif e.original.code == 401:
                    raise plugin.PluginError(
                        "Username/password for transmission is incorrect. Cannot connect."
                    )
                elif e.original.code == 110:
                    raise plugin.PluginError(
                        "Cannot connect to transmission: Connection timed out."
                    )
                else:
                    raise plugin.PluginError(
                        "Error connecting to transmission: %s" % e.original.message
                    )
            else:
                raise plugin.PluginError("Error connecting to transmission: %s" % e.message)
        return cli

    def torrent_info(self, torrent, config):
        done = torrent.totalSize > 0
        vloc = None
        best = None
        for t in torrent.files().items():
            tf = t[1]
            if tf['selected']:
                if tf['size'] <= 0 or tf['completed'] < tf['size']:
                    done = False
                    break
                if not best or tf['size'] > best[1]:
                    best = (tf['name'], tf['size'])
        if (
            done
            and best
            and (100 * float(best[1]) / float(torrent.totalSize))
            >= (config['main_file_ratio'] * 100)
        ):
            vloc = ('%s/%s' % (torrent.downloadDir, best[0])).replace('/', os.sep)
        return done, vloc

    def check_seed_limits(self, torrent, session):
        seed_limit_ok = True  # will remain if no seed ratio defined
        idle_limit_ok = True  # will remain if no idle limit defined

        if torrent.seedRatioMode == 1:  # use torrent's own seed ratio limit
            seed_limit_ok = torrent.uploadRatio >= torrent.seedRatioLimit
        elif torrent.seedRatioMode == 0:  # use global rules
            if session.seedRatioLimited:
                seed_limit_ok = torrent.uploadRatio >= session.seedRatioLimit

        if torrent.seedIdleMode == 1:  # use torrent's own idle limit
            idle_limit_ok = (
                torrent.date_active + timedelta(minutes=torrent.seedIdleLimit) < datetime.now()
            )
        elif torrent.seedIdleMode == 0:  # use global rules
            if session.idle_seeding_limit_enabled:
                idle_limit_ok = (
                    torrent.date_active + timedelta(minutes=session.idle_seeding_limit)
                    < datetime.now()
                )

        return seed_limit_ok, idle_limit_ok

    def on_task_start(self, task, config):
        try:
            import transmissionrpc
            from transmissionrpc import TransmissionError  # noqa
            from transmissionrpc import HTTPHandlerError  # noqa
        except:
            raise plugin.PluginError(
                'Transmissionrpc module version 0.11 or higher required.', log
            )
        if [int(part) for part in transmissionrpc.__version__.split('.')] < [0, 11]:
            raise plugin.PluginError(
                'Transmissionrpc module version 0.11 or higher required, please upgrade', log
            )

        # Mark rpc client for garbage collector so every task can start
        # a fresh new according its own config - fix to bug #2804
        self.client = None
        config = self.prepare_config(config)
        if config['enabled']:
            if task.options.test:
                log.info('Trying to connect to transmission...')
                self.client = self.create_rpc_client(config)
                if self.client:
                    log.info('Successfully connected to transmission.')
                else:
                    log.error('It looks like there was a problem connecting to transmission.')


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

        if not self.client:
            self.client = self.create_rpc_client(config)
        entries = []

        # Hack/Workaround for http://flexget.com/ticket/2002
        # TODO: Proper fix
        if 'username' in config and 'password' in config:
            self.client.http_handler.set_authentication(
                self.client.url, config['username'], config['password']
            )

        session = self.client.get_session()

        for torrent in self.client.get_torrents():
            seed_ratio_ok, idle_limit_ok = self.check_seed_limits(torrent, session)
            if config['only_complete'] and not (
                seed_ratio_ok and idle_limit_ok and torrent.progress == 100
            ):
                continue
            entry = Entry(
                title=torrent.name,
                url='',
                torrent_info_hash=torrent.hashString,
                content_size=torrent.totalSize / (1024 * 1024),
            )
            # Location of torrent is only valid if transmission is on same machine as flexget
            if config['host'] in ('localhost', '127.0.0.1'):
                entry['location'] = torrent.torrentFile
                entry['url'] = 'file://' + torrent.torrentFile
            for attr in [
                'id',
                'comment',
                'downloadDir',
                'isFinished',
                'isPrivate',
                'ratio',
                'status',
                'date_active',
                'date_added',
                'date_done',
                'date_started',
                'priority',
                'progress',
                'secondsDownloading',
                'secondsSeeding',
            ]:
                try:
                    entry['transmission_' + attr] = getattr(torrent, attr)
                except Exception:
                    log.debug(
                        'error when requesting transmissionrpc attribute %s', attr, exc_info=True
                    )
            entry['transmission_trackers'] = [t['announce'] for t in torrent.trackers]
            entry['transmission_seed_ratio_ok'] = seed_ratio_ok
            entry['transmission_idle_limit_ok'] = idle_limit_ok
            # Built in done_date doesn't work when user adds an already completed file to transmission
            if torrent.progress == 100:
                entry['transmission_date_done'] = datetime.fromtimestamp(
                    max(torrent.addedDate, torrent.doneDate)
                )
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
                        'enum': ['add', 'remove', 'purge', 'pause', 'resume'],
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
        if self.client is None:
            self.client = self.create_rpc_client(config)
            if self.client:
                log.debug('Successfully connected to transmission.')
            else:
                raise plugin.PluginError("Couldn't connect to transmission.")
        session_torrents = self.client.get_torrents()
        for entry in task.accepted:
            if task.options.test:
                log.info('Would %s %s in transmission.', config['action'], entry['title'])
                continue
            # Compile user options into appropriate dict
            options = self._make_torrent_options_dict(config, entry)
            torrent_info = None
            for t in session_torrents:
                if t.hashString.lower() == entry.get(
                    'torrent_info_hash', ''
                ).lower() or t.id == entry.get('transmission_id'):
                    torrent_info = t
                    log.debug(
                        'Found %s already loaded in transmission as %s',
                        entry['title'],
                        torrent_info.name,
                    )
                    break

            if not torrent_info:
                if config['action'] != 'add':
                    log.warning(
                        'Cannot %s %s because it is not loaded in transmission.',
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
                    log.debug('entry: %s', entry)
                    log.debug('temp: %s', ', '.join(os.listdir(tmp_path)))
                    entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                    continue

                try:
                    if downloaded:
                        with open(entry['file'], 'rb') as f:
                            filedump = base64.b64encode(f.read()).decode('utf-8')
                        torrent_info = self.client.add_torrent(filedump, 30, **options['add'])
                    else:
                        # we need to set paused to false so the magnetization begins immediately
                        options['add']['paused'] = False
                        torrent_info = self.client.add_torrent(
                            entry['url'], timeout=30, **options['add']
                        )
                except TransmissionError as e:
                    log.debug('TransmissionError', exc_info=True)
                    log.debug('Failed options dict: %s', options['add'])
                    msg = 'Error adding {} to transmission. TransmissionError: {}'.format(
                        entry['title'], e.message or 'N/A'
                    )
                    log.error(msg)
                    entry.fail(msg)
                    continue
                log.info('"%s" torrent added to transmission', entry['title'])
                # The info returned by the add call is incomplete, refresh it
                torrent_info = self.client.get_torrent(torrent_info.id)

            try:
                total_size = torrent_info.totalSize
                main_id = None
                find_main_file = (
                    options['post'].get('main_file_only') or 'content_filename' in options['post']
                )
                skip_files = options['post'].get('skip_files')
                # We need to index the files if any of the following are defined
                if find_main_file or skip_files:
                    file_list = self.client.get_files(torrent_info.id)[torrent_info.id]

                    if options['post'].get('magnetization_timeout', 0) > 0 and not file_list:
                        log.debug(
                            'Waiting %d seconds for "%s" to magnetize',
                            options['post']['magnetization_timeout'],
                            entry['title'],
                        )
                        for _ in range(options['post']['magnetization_timeout']):
                            sleep(1)
                            file_list = self.client.get_files(torrent_info.id)[torrent_info.id]
                            if file_list:
                                total_size = self.client.get_torrent(
                                    torrent_info.id, ['id', 'totalSize']
                                ).totalSize
                                break
                        else:
                            log.warning(
                                '"%s" did not magnetize before the timeout elapsed, '
                                'file list unavailable for processing.',
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

                    for f in file_list:
                        # No need to set main_id if we're not going to need it
                        if find_main_file and file_list[f]['size'] > total_size * main_ratio:
                            main_id = f

                        if 'include_files' in options['post']:
                            if any(
                                fnmatch(file_list[f]['name'], mask)
                                for mask in options['post']['include_files']
                            ):
                                dl_list.append(f)
                            elif options['post'].get('include_subs') and any(
                                fnmatch(file_list[f]['name'], mask) for mask in ext_list
                            ):
                                dl_list.append(f)

                        if skip_files:
                            if any(fnmatch(file_list[f]['name'], mask) for mask in skip_files):
                                skip_list.append(f)

                    if main_id is not None:
                        # Look for files matching main ID title but with a different extension
                        if options['post'].get('rename_like_files'):
                            for f in file_list:
                                # if this filename matches main filename we want to rename it as well
                                fs = os.path.splitext(file_list[f]['name'])
                                if fs[0] == os.path.splitext(file_list[main_id]['name'])[0]:
                                    main_list.append(f)
                        else:
                            main_list = [main_id]

                        if main_id not in dl_list:
                            dl_list.append(main_id)
                    elif find_main_file:
                        log.warning(
                            'No files in "%s" are > %d%% of content size, no files renamed.',
                            entry['title'],
                            main_ratio * 100,
                        )

                    # If we have a main file and want to rename it and associated files
                    if 'content_filename' in options['post'] and main_id is not None:
                        if 'download_dir' not in options['add']:
                            download_dir = self.client.get_session().download_dir
                        else:
                            download_dir = options['add']['download_dir']

                        # Get new filename without ext
                        file_ext = os.path.splitext(file_list[main_id]['name'])[1]
                        file_path = os.path.dirname(
                            os.path.join(download_dir, file_list[main_id]['name'])
                        )
                        filename = options['post']['content_filename']
                        if config['host'] == 'localhost' or config['host'] == '127.0.0.1':
                            counter = 1
                            while os.path.exists(os.path.join(file_path, filename + file_ext)):
                                # Try appending a (#) suffix till a unique filename is found
                                filename = '%s(%s)' % (
                                    options['post']['content_filename'],
                                    counter,
                                )
                                counter += 1
                        else:
                            log.debug(
                                'Cannot ensure content_filename is unique '
                                'when adding to a remote transmission daemon.'
                            )

                        for index in main_list:
                            file_ext = os.path.splitext(file_list[index]['name'])[1]
                            log.debug(
                                'File %s renamed to %s'
                                % (file_list[index]['name'], filename + file_ext)
                            )
                            # change to below when set_files will allow setting name, more efficient to have one call
                            # fl[index]['name'] = os.path.basename(pathscrub(filename + file_ext).encode('utf-8'))
                            try:
                                self.client.rename_torrent_path(
                                    torrent_info.id,
                                    file_list[index]['name'],
                                    os.path.basename(str(pathscrub(filename + file_ext))),
                                )
                            except TransmissionError:
                                log.error('content_filename only supported with transmission 2.8+')

                    if options['post'].get('main_file_only') and main_id is not None:
                        # Set Unwanted Files
                        options['change']['files_unwanted'] = [
                            x for x in file_list if x not in dl_list
                        ]
                        options['change']['files_wanted'] = dl_list
                        log.debug(
                            'Downloading %s of %s files in torrent.',
                            len(options['change']['files_wanted']),
                            len(file_list),
                        )
                    elif (
                        not options['post'].get('main_file_only') or main_id is None
                    ) and skip_files:
                        # If no main file and we want to skip files

                        if len(skip_list) >= len(file_list):
                            log.debug(
                                'skip_files filter would cause no files to be downloaded; '
                                'including all files in torrent.'
                            )
                        else:
                            options['change']['files_unwanted'] = skip_list
                            options['change']['files_wanted'] = [
                                x for x in file_list if x not in skip_list
                            ]
                            log.debug(
                                'Downloading %s of %s files in torrent.',
                                len(options['change']['files_wanted']),
                                len(file_list),
                            )

                # Set any changed file properties
                if list(options['change'].keys()):
                    self.client.change_torrent(torrent_info.id, 30, **options['change'])

                if config['action'] == 'add':
                    # if add_paused was defined and set to False start the torrent;
                    # prevents downloading data before we set what files we want
                    start_paused = (
                        options['post']['paused']
                        if 'paused' in options['post']
                        else not self.client.get_session().start_added_torrents
                    )
                    if start_paused:
                        self.client.stop_torrent(torrent_info.id)
                    else:
                        self.client.start_torrent(torrent_info.id)
                elif config['action'] in ('remove', 'purge'):
                    self.client.remove_torrent(
                        [torrent_info.id], delete_data=config['action'] == 'purge'
                    )
                    log.info('%sd %s from transmission', config['action'], torrent_info.name)
                elif config['action'] == 'pause':
                    self.client.stop_torrent([torrent_info.id])
                    log.info('paused %s in transmission', torrent_info.name)
                elif config['action'] == 'resume':
                    self.client.start_torrent([torrent_info.id])
                    log.info('resumed %s in transmission', torrent_info.name)

            except TransmissionError as e:
                log.debug('TransmissionError', exc_info=True)
                log.debug('Failed options dict: %s', options)
                msg = 'Error trying to {} {}, TransmissionError: {}'.format(
                    config['action'], entry['title'], e.message or 'N/A'
                )
                log.error(msg)
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
                log.error('Error setting path for %s: %s' % (entry['title'], e))
            else:
                # Transmission doesn't like it when paths end in a separator
                path = path.rstrip('\\/')
                add['download_dir'] = text_to_native_str(pathscrub(path), 'utf-8')
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
                log.error('Unable to render content_filename %s: %s' % (entry['title'], e))
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
        """ Make sure all temp files are cleaned up when entries are learned """
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
        if not self.client:
            self.client = self.create_rpc_client(config)
        tracker_re = re.compile(config['tracker'], re.IGNORECASE) if 'tracker' in config else None
        preserve_tracker_re = (
            re.compile(config['preserve_tracker'], re.IGNORECASE)
            if 'preserve_tracker' in config
            else None
        )

        session = self.client.get_session()

        remove_ids = []
        for torrent in self.client.get_torrents():
            log.verbose(
                'Torrent "%s": status: "%s" - ratio: %s -  date added: %s'
                % (torrent.name, torrent.status, torrent.ratio, torrent.date_added)
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
                started_seeding = datetime.fromtimestamp(max(torrent.addedDate, torrent.doneDate))
                if started_seeding + parse_timedelta(config['finished_for']) > datetime.now():
                    continue
            tracker_hosts = (
                urlparse(tracker['announce']).hostname for tracker in torrent.trackers
            )
            if 'tracker' in config:
                if not any(tracker_re.search(tracker) for tracker in tracker_hosts):
                    continue
            if 'preserve_tracker' in config:
                if any(preserve_tracker_re.search(tracker) for tracker in tracker_hosts):
                    continue
            if config.get('directories'):
                if not any(
                    re.search(d, torrent.downloadDir, re.IGNORECASE) for d in config['directories']
                ):
                    continue
            if task.options.test:
                log.info('Would remove finished torrent `%s` from transmission', torrent.name)
                continue
            log.info('Removing finished torrent `%s` from transmission', torrent.name)
            remove_ids.append(torrent.id)
        if remove_ids:
            self.client.remove_torrent(remove_ids, config.get('delete_files'))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTransmission, 'transmission', api_ver=2)
    plugin.register(PluginTransmissionInput, 'from_transmission', api_ver=2)
    plugin.register(PluginTransmissionClean, 'clean_transmission', api_ver=2)
