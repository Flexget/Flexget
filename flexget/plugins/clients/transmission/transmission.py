from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring
from future.utils import text_to_native_str

import os
import logging
import base64
import time
from datetime import datetime
from datetime import timedelta
from netrc import netrc, NetrcParseError

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub

from flexget.config_schema import one_or_more
from fnmatch import fnmatch

from .client import create_rpc_client

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

    def _validator(self, advanced):
        """Return config validator"""
        advanced.accept('text', key='host')
        advanced.accept('integer', key='port')
        # note that password is optional in transmission
        advanced.accept('file', key='netrc')
        advanced.accept('text', key='username')
        advanced.accept('text', key='password')
        advanced.accept('boolean', key='enabled')
        return advanced

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
                config['username'], _, config['password'] = netrc(netrc_path).authenticators(config['host'])
            except IOError as e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError as e:
                log.error('netrc: %s, file: %s, line: %s' % (e.msg, e.filename, e.lineno))
        return config

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
        if done and best and (100 * float(best[1]) / float(torrent.totalSize)) >= (config['main_file_ratio'] * 100):
            vloc = ('%s/%s' % (torrent.downloadDir, best[0])).replace('/', os.sep)
        return done, vloc

    def check_seed_limits(self, torrent, session):
        seed_limit_ok = None  # will remain if no seed ratio defined
        idle_limit_ok = None  # will remain if no idle limit defined

        if torrent.seedRatioMode == 1:  # use torrent's own seed ratio limit
            seed_limit_ok = torrent.uploadRatio >= torrent.seedRatioLimit
        elif torrent.seedRatioMode == 0:  # use global rules
            if session.seedRatioLimited:
                seed_limit_ok = torrent.uploadRatio >= session.seedRatioLimit

        if torrent.seedIdleMode == 1:  # use torrent's own idle limit
            idle_limit_ok = torrent.date_active + timedelta(minutes=torrent.seedIdleLimit) < datetime.now()
        elif torrent.seedIdleMode == 0:  # use global rules
            if session.idle_seeding_limit_enabled:
                idle_limit_ok = torrent.date_active + timedelta(minutes=session.idle_seeding_limit) < datetime.now()

        return seed_limit_ok, idle_limit_ok

    def on_task_start(self, task, config):
        try:
            import transmissionrpc
            from transmissionrpc import TransmissionError  # noqa
            from transmissionrpc import HTTPHandlerError  # noqa
        except:
            raise plugin.PluginError('Transmissionrpc module version 0.11 or higher required.', log)
        if [int(part) for part in transmissionrpc.__version__.split('.')] < [0, 11]:
            raise plugin.PluginError('Transmissionrpc module version 0.11 or higher required, please upgrade', log)

        # Mark rpc client for garbage collector so every task can start
        # a fresh new according its own config - fix to bug #2804
        self.client = None
        config = self.prepare_config(config)
        if config['enabled']:
            if task.options.test:
                log.info('Trying to connect to transmission...')
                self.client = create_rpc_client(config)
                if self.client:
                    log.info('Successfully connected to transmission.')
                else:
                    log.error('It looks like there was a problem connecting to transmission.')


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
                    'path': {'type': 'string'},
                    'maxupspeed': {'type': 'number'},
                    'maxdownspeed': {'type': 'number'},
                    'maxconnections': {'type': 'integer'},
                    'ratio': {'type': 'number'},
                    'addpaused': {'type': 'boolean'},
                    'content_filename': {'type': 'string'},
                    'main_file_only': {'type': 'boolean'},
                    'main_file_ratio': {'type': 'number'},
                    'magnetization_timeout': {'type': 'integer'},
                    'enabled': {'type': 'boolean'},
                    'include_subs': {'type': 'boolean'},
                    'bandwidthpriority': {'type': 'number'},
                    'honourlimits': {'type': 'boolean'},
                    'include_files': one_or_more({'type': 'string'}),
                    'skip_files': one_or_more({'type': 'string'}),
                    'rename_like_files': {'type': 'boolean'},
                    'queue_position': {'type': 'integer'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        config = TransmissionBase.prepare_config(self, config)
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
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

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
            self.client = create_rpc_client(config)
            if self.client:
                log.debug('Successfully connected to transmission.')
            else:
                raise plugin.PluginError("Couldn't connect to transmission.")
        if task.accepted:
            self.add_to_transmission(self.client, task, config)

    def _make_torrent_options_dict(self, config, entry):

        opt_dic = {}

        for opt_key in ('path', 'addpaused', 'honourlimits', 'bandwidthpriority', 'maxconnections', 'maxupspeed',
                        'maxdownspeed', 'ratio', 'main_file_only', 'main_file_ratio', 'magnetization_timeout',
                        'include_subs', 'content_filename', 'include_files', 'skip_files', 'rename_like_files',
                        'queue_position'):
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
                add['download_dir'] = text_to_native_str(pathscrub(path), 'utf-8')
            except RenderError as e:
                log.error('Error setting path for %s: %s' % (entry['title'], e))
        if 'bandwidthpriority' in opt_dic:
            add['bandwidthPriority'] = opt_dic['bandwidthpriority']
        if 'maxconnections' in opt_dic:
            add['peer_limit'] = opt_dic['maxconnections']
        # make sure we add it paused, will modify status after adding
        add['paused'] = True

        change = options['change']
        if 'honourlimits' in opt_dic and not opt_dic['honourlimits']:
            change['honorsSessionLimits'] = False
        if 'maxupspeed' in opt_dic:
            change['uploadLimit'] = opt_dic['maxupspeed']
            change['uploadLimited'] = True
        if 'maxdownspeed' in opt_dic:
            change['downloadLimit'] = opt_dic['maxdownspeed']
            change['downloadLimited'] = True

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
        if 'addpaused' in opt_dic:
            post['paused'] = opt_dic['addpaused']
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
        if 'include_files' in opt_dic:
            post['include_files'] = opt_dic['include_files']
        if 'rename_like_files' in opt_dic:
            post['rename_like_files'] = opt_dic['rename_like_files']
        return options

    def add_to_transmission(self, cli, task, config):
        """Adds accepted entries to transmission """
        for entry in task.accepted:
            if task.options.test:
                log.info('Would add %s to transmission' % entry['url'])
                continue
            # Compile user options into appripriate dict
            options = self._make_torrent_options_dict(config, entry)
            downloaded = not entry['url'].startswith('magnet:')

            # Check that file is downloaded
            if downloaded and 'file' not in entry:
                entry.fail('file missing?')
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
                    r = cli.add_torrent(filedump, 30, **options['add'])
                else:
                    # we need to set paused to false so the magnetization begins immediately
                    options['add']['paused'] = False
                    r = cli.add_torrent(entry['url'], timeout=30, **options['add'])

                log.info('"%s" torrent added to transmission', entry['title'])

                total_size = cli.get_torrent(r.id, ['id', 'totalSize']).totalSize

                def _filter_list(list):
                    for item in list:
                        if not isinstance(item, basestring):
                            list.remove(item)
                    return list

                def _find_matches(name, list):
                    for mask in list:
                        if fnmatch(name, mask):
                            return True
                    return False

                def _wait_for_files(cli, r, timeout):
                    from time import sleep
                    while timeout > 0:
                        sleep(1)
                        fl = cli.get_files(r.id)
                        if len(fl[r.id]) > 0:
                            return fl
                        else:
                            timeout -= 1
                    return fl

                skip_files = False
                # Filter list because "set" plugin doesn't validate based on schema
                # Skip files only used if we have no main file
                if 'skip_files' in options['post']:
                    skip_files = True
                    options['post']['skip_files'] = _filter_list(options['post']['skip_files'])

                main_id = None
                find_main_file = options['post'].get('main_file_only') or 'content_filename' in options['post']
                # We need to index the files if any of the following are defined
                if find_main_file or skip_files:
                    fl = cli.get_files(r.id)

                    if ('magnetization_timeout' in options['post'] and
                                options['post']['magnetization_timeout'] > 0 and
                            not downloaded and
                                len(fl[r.id]) == 0):
                        log.debug('Waiting %d seconds for "%s" to magnetize', options['post']['magnetization_timeout'],
                                  entry['title'])
                        fl = _wait_for_files(cli, r, options['post']['magnetization_timeout'])
                        if len(fl[r.id]) == 0:
                            log.warning('"%s" did not magnetize before the timeout elapsed, '
                                        'file list unavailable for processing.', entry['title'])
                        else:
                            total_size = cli.get_torrent(r.id, ['id', 'totalSize']).totalSize

                    # Find files based on config
                    dl_list = []
                    skip_list = []
                    main_list = []
                    full_list = []
                    ext_list = ['*.srt', '*.sub', '*.idx', '*.ssa', '*.ass']

                    main_ratio = config['main_file_ratio']
                    if 'main_file_ratio' in options['post']:
                        main_ratio = options['post']['main_file_ratio']

                    if 'include_files' in options['post']:
                        options['post']['include_files'] = _filter_list(options['post']['include_files'])

                    for f in fl[r.id]:
                        full_list.append(f)
                        # No need to set main_id if we're not going to need it
                        if find_main_file and fl[r.id][f]['size'] > total_size * main_ratio:
                            main_id = f

                        if 'include_files' in options['post']:
                            if _find_matches(fl[r.id][f]['name'], options['post']['include_files']):
                                dl_list.append(f)
                            elif options['post'].get('include_subs') and _find_matches(fl[r.id][f]['name'], ext_list):
                                dl_list.append(f)

                        if skip_files:
                            if _find_matches(fl[r.id][f]['name'], options['post']['skip_files']):
                                skip_list.append(f)

                    if main_id is not None:

                        # Look for files matching main ID title but with a different extension
                        if options['post'].get('rename_like_files'):
                            for f in fl[r.id]:
                                # if this filename matches main filename we want to rename it as well
                                fs = os.path.splitext(fl[r.id][f]['name'])
                                if fs[0] == os.path.splitext(fl[r.id][main_id]['name'])[0]:
                                    main_list.append(f)
                        else:
                            main_list = [main_id]

                        if main_id not in dl_list:
                            dl_list.append(main_id)
                    elif find_main_file:
                        log.warning('No files in "%s" are > %d%% of content size, no files renamed.',
                                    entry['title'], main_ratio * 100)

                    # If we have a main file and want to rename it and associated files
                    if 'content_filename' in options['post'] and main_id is not None:
                        if 'download_dir' not in options['add']:
                            download_dir = cli.get_session().download_dir
                        else:
                            download_dir = options['add']['download_dir']

                        # Get new filename without ext
                        file_ext = os.path.splitext(fl[r.id][main_id]['name'])[1]
                        file_path = os.path.dirname(os.path.join(download_dir, fl[r.id][main_id]['name']))
                        filename = options['post']['content_filename']
                        if config['host'] == 'localhost' or config['host'] == '127.0.0.1':
                            counter = 1
                            while os.path.exists(os.path.join(file_path, filename + file_ext)):
                                # Try appending a (#) suffix till a unique filename is found
                                filename = '%s(%s)' % (options['post']['content_filename'], counter)
                                counter += 1
                        else:
                            log.debug('Cannot ensure content_filename is unique '
                                      'when adding to a remote transmission daemon.')

                        for index in main_list:
                            file_ext = os.path.splitext(fl[r.id][index]['name'])[1]
                            log.debug('File %s renamed to %s' % (fl[r.id][index]['name'], filename + file_ext))
                            # change to below when set_files will allow setting name, more efficient to have one call
                            # fl[r.id][index]['name'] = os.path.basename(pathscrub(filename + file_ext).encode('utf-8'))
                            try:
                                cli.rename_torrent_path(r.id, fl[r.id][index]['name'],
                                                        os.path.basename(str(pathscrub(filename + file_ext))))
                            except TransmissionError:
                                log.error('content_filename only supported with transmission 2.8+')

                    if options['post'].get('main_file_only') and main_id is not None:
                        # Set Unwanted Files
                        options['change']['files_unwanted'] = [x for x in full_list if x not in dl_list]
                        options['change']['files_wanted'] = dl_list
                        log.debug('Downloading %s of %s files in torrent.',
                                  len(options['change']['files_wanted']), len(full_list))
                    elif (not options['post'].get('main_file_only') or main_id is None) and skip_files:
                        # If no main file and we want to skip files

                        if len(skip_list) >= len(full_list):
                            log.debug('skip_files filter would cause no files to be downloaded; '
                                      'including all files in torrent.')
                        else:
                            options['change']['files_unwanted'] = skip_list
                            options['change']['files_wanted'] = [x for x in full_list if x not in skip_list]
                            log.debug('Downloading %s of %s files in torrent.',
                                      len(options['change']['files_wanted']), len(full_list))

                # Set any changed file properties
                if list(options['change'].keys()):
                    cli.change_torrent(r.id, 30, **options['change'])

                # if addpaused was defined and set to False start the torrent;
                # prevents downloading data before we set what files we want
                if ('paused' in options['post'] and not options['post']['paused'] or
                                'paused' not in options['post'] and cli.get_session().start_added_torrents):
                    cli.start_torrent(r.id)
                elif options['post'].get('paused'):
                    log.debug('sleeping 5s to stop the torrent...')
                    time.sleep(5)
                    cli.stop_torrent(r.id)
                    log.info('Torrent "%s" stopped because of addpaused=yes', entry['title'])

            except TransmissionError as e:
                log.debug('TransmissionError', exc_info=True)
                log.debug('Failed options dict: %s', options)
                msg = 'TransmissionError: %s' % e.message or 'N/A'
                log.error(msg)
                entry.fail(msg)

    def on_task_learn(self, task, config):
        """ Make sure all temp files are cleaned up when entries are learned """
        # If download plugin is enabled, it will handle cleanup.
        if 'download' not in task.config:
            download = plugin.get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    on_task_abort = on_task_learn


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTransmission, 'transmission', api_ver=2)
