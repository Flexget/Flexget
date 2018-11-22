import os
import time
import base64
from fnmatch import fnmatch
from datetime import datetime
from datetime import timedelta
from past.builtins import basestring

from flexget import plugin
from flexget.utils.pathscrub import pathscrub

from .transmission import log
from .utils import create_torrent_options

try:
    import transmissionrpc
    from transmissionrpc import TransmissionError
    from transmissionrpc import HTTPHandlerError
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    pass


def create_rpc_client(config):
    user, password = config.get('username'), config.get('password')

    try:
        return transmissionrpc.Client(config['host'], config['port'], user, password)
    except TransmissionError as e:
        if isinstance(e.original, HTTPHandlerError):
            if e.original.code == 111:
                raise plugin.PluginError("Cannot connect to transmission. Is it running?")
            elif e.original.code == 401:
                raise plugin.PluginError("Username/password for transmission is incorrect. Cannot connect.")
            elif e.original.code == 110:
                raise plugin.PluginError("Cannot connect to transmission: Connection timed out.")
            else:
                raise plugin.PluginError("Error connecting to transmission: %s" % e.original.message)
        else:
            raise plugin.PluginError("Error connecting to transmission: %s" % e.message)


def add_to_transmission(cli, task, config):
    """Adds accepted entries to transmission """
    for entry in task.accepted:
        if task.options.test:
            log.info('Would add %s to transmission' % entry['url'])
            continue
        # Compile user options into appropriate dict
        options = create_torrent_options(config, entry)
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


def torrent_info(torrent, config):
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


def check_seed_limits(torrent, session):
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
