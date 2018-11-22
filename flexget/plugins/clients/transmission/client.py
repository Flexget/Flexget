import os
import time
import base64
import logging
from fnmatch import fnmatch
from past.builtins import basestring

from flexget import plugin
from flexget.utils.pathscrub import pathscrub

from flexget.plugins.clients.transmission.utils import create_torrent_options

try:
    import transmissionrpc
    from transmissionrpc import TransmissionError
    from transmissionrpc import HTTPHandlerError
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    pass

log = logging.getLogger('transmission')


# TODO: maybe cache client
def create_rpc_client(config):
    user, password = config.get('username'), config.get('password')

    try:
        client = transmissionrpc.Client(config['host'], config['port'], user, password)
        log.info('Successfully connected to transmission.')
        return client
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

        # TODO: find more appropriate name
        class Data:
            def __init__(self, entry, cli, task, config):
                self.cli = cli
                self.task = task
                self.entry = entry
                self.config = config

                # Compile user options into appropriate dict
                self.options = create_torrent_options(config, entry)
                self.downloaded = not entry['url'].startswith('magnet:')

            @staticmethod
            def filter_list(list_):
                for item in list_:
                    if not isinstance(item, basestring):
                        list_.remove(item)
                return list_

            @staticmethod
            def find_matches(name, list_):
                for mask in list_:
                    if fnmatch(name, mask):
                        return True
                return False

            def wait_for_files(self):
                from time import sleep
                timeout = self.options['post']['magnetization_timeout']

                while timeout > 0:
                    sleep(1)
                    fl = self.cli.get_files(self.torrent.id)
                    if len(fl[self.torrent.id]) > 0:
                        return fl
                    else:
                        timeout -= 1
                return fl

        data = Data(entry, cli, task, config)

        # Check that file is downloaded
        if data.downloaded and 'file' not in data.entry:
            data.entry.fail('file missing?')
            continue

        # Verify the temp file exists
        if data.downloaded and not os.path.exists(entry['file']):
            tmp_path = os.path.join(data.task.manager.config_base, 'temp')
            log.debug('entry: %s', entry)
            log.debug('temp: %s', ', '.join(os.listdir(tmp_path)))
            entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
            continue

        try:
            if data.downloaded:
                with open(data.entry['file'], 'rb') as f:
                    filedump = base64.b64encode(f.read()).decode('utf-8')
                    data.torrent = data.cli.add_torrent(filedump, 30, **data.options['add'])
            else:
                # we need to set paused to false so the magnetization begins immediately
                data.options['add']['paused'] = False
                data.torrent = data.cli.add_torrent(entry['url'], timeout=30, **data.options['add'])

            log.info('"%s" torrent added to transmission', data.entry['title'])

            data.total_size = data.cli.get_torrent(data.torrent.id, ['id', 'totalSize']).totalSize

            data.skip_files = False
            # Filter list because "set" plugin doesn't validate based on schema
            # Skip files only used if we have no main file
            if 'skip_files' in data.options['post']:
                data.skip_files = True
                data.options['post']['skip_files'] = data.filter_list(data.options['post']['skip_files'])

            data.find_main_file = data.options['post'].get('main_file_only') \
                                  or 'content_filename' in data.options['post']

            # We need to index the files if any of the following are defined
            if data.find_main_file or data.skip_files:
                _index_file(data)

            # Set any changed file properties
            if list(data.options['change'].keys()):
                data.cli.change_torrent(data.torrent.id, 30, **data.options['change'])

            # if addpaused was defined and set to False start the torrent;
            # prevents downloading data before we set what files we want
            _start_or_stop_torrent(data)

        except TransmissionError as e:
            log.debug('TransmissionError', exc_info=True)
            log.debug('Failed options dict: %s', data.options)
            msg = 'TransmissionError: %s' % e.message or 'N/A'
            log.error(msg)
            entry.fail(msg)


def _start_or_stop_torrent(data):
    if ('paused' in data.options['post'] and not data.options['post']['paused'] or
                    'paused' not in data.options['post'] and data.cli.get_session().start_added_torrents):
        data.cli.start_torrent(data.torrent.id)
    elif data.options['post'].get('paused'):
        log.debug('sleeping 5s to stop the torrent...')
        time.sleep(5)
        data.cli.stop_torrent(data.torrent.id)
        log.info('Torrent "%s" stopped because of addpaused=yes', data.entry['title'])


def _wait_for_magnetization_if_needed(data):
    conditions = [not data.downloaded,
                  data.options['post']['magnetization_timeout'] > 0,
                  'magnetization_timeout' in data.options['post'],
                  len(data.files[data.torrent.id]) == 0]

    if all(conditions):
        log.debug('Waiting %d seconds for "%s" to magnetize', data.options['post']['magnetization_timeout'],
                  data.entry['title'])
        fl = data.wait_for_files()
        if len(fl[data.torrent.id]) == 0:
            log.warning('"%s" did not magnetize before the timeout elapsed, '
                        'file list unavailable for processing.', data.entry['title'])
        else:
            data.total_size = data.cli.get_torrent(data.torrent.id, ['id', 'totalSize']).totalSize


def _index_file(data):
    data.files = data.cli.get_files(data.torrent.id)
    _wait_for_magnetization_if_needed(data)

    # Find files based on config
    dl_list = []
    skip_list = []
    main_list = []
    full_list = []
    ext_list = ['*.srt', '*.sub', '*.idx', '*.ssa', '*.ass']

    main_ratio = data.config['main_file_ratio']
    if 'main_file_ratio' in data.options['post']:
        main_ratio = data.options['post']['main_file_ratio']

    if 'include_files' in data.options['post']:
        data.options['post']['include_files'] = data.filter_list(data.options['post']['include_files'])

    for f in data.files[data.torrent.id]:
        full_list.append(f)
        # No need to set main_id if we're not going to need it
        if data.find_main_file and data.files[data.torrent.id][f]['size'] > data.total_size * main_ratio:
            main_id = f

        if 'include_files' in data.options['post']:
            if data.find_matches(data.files[data.torrent.id][f]['name'], data.options['post']['include_files']):
                dl_list.append(f)
            elif data.options['post'].get('include_subs') and data.find_matches(data.files[data.torrent.id][f]['name'],
                                                                                ext_list):
                dl_list.append(f)

        if data.skip_files:
            if data.find_matches(data.files[data.torrent.id][f]['name'],
                                 data.options['post']['skip_files']):
                skip_list.append(f)

    if main_id is not None:

        # Look for files matching main ID title but with a different extension
        if data.options['post'].get('rename_like_files'):
            for f in data.files[data.torrent.id]:
                # if this filename matches main filename we want to rename it as well
                fs = os.path.splitext(data.files[data.torrent.id][f]['name'])
                if fs[0] == os.path.splitext(data.files[data.torrent.id][main_id]['name'])[0]:
                    main_list.append(f)
        else:
            main_list = [main_id]

        if main_id not in dl_list:
            dl_list.append(main_id)
    elif data.find_main_file:
        log.warning('No files in "%s" are > %d%% of content size, no files renamed.', data.entry['title'],
                    main_ratio * 100)

    # If we have a main file and want to rename it and associated files
    if 'content_filename' in data.options['post'] and main_id is not None:
        if 'download_dir' not in data.options['add']:
            download_dir = data.cli.get_session().download_dir
        else:
            download_dir = data.options['add']['download_dir']

        # Get new filename without ext
        file_ext = os.path.splitext(data.files[data.torrent.id][main_id]['name'])[1]
        file_path = os.path.dirname(
            os.path.join(download_dir, data.files[data.torrent.id][main_id]['name']))
        filename = data.options['post']['content_filename']
        if data.config['host'] == 'localhost' or data.config['host'] == '127.0.0.1':
            counter = 1
            while os.path.exists(os.path.join(file_path, filename + file_ext)):
                # Try appending a (#) suffix till a unique filename is found
                filename = '%s(%s)' % (data.options['post']['content_filename'], counter)
                counter += 1
        else:
            log.debug('Cannot ensure content_filename is unique '
                      'when adding to a remote transmission daemon.')

        for index in main_list:
            file_ext = os.path.splitext(data.files[data.torrent.id][index]['name'])[1]
            log.debug('File %s renamed to %s' % (
                data.files[data.torrent.id][index]['name'], filename + file_ext))
            # change to below when set_files will allow setting name, more efficient to have one call
            # fl[r.id][index]['name'] = os.path.basename(pathscrub(filename + file_ext).encode('utf-8'))
            try:
                data.cli.rename_torrent_path(data.torrent.id, data.files[data.torrent.id][index]['name'],
                                             os.path.basename(str(pathscrub(filename + file_ext))))
            except TransmissionError:
                log.error('content_filename only supported with transmission 2.8+')

    if data.options['post'].get('main_file_only') and main_id is not None:
        # Set Unwanted Files
        data.options['change']['files_unwanted'] = [x for x in full_list if x not in dl_list]
        data.options['change']['files_wanted'] = dl_list
        log.debug('Downloading %s of %s files in torrent.',
                  len(data.options['change']['files_wanted']), len(full_list))
    elif data.skip_files and (not data.options['post'].get('main_file_only') or main_id is None):
        # If no main file and we want to skip files

        if len(skip_list) >= len(full_list):
            log.debug('skip_files filter would cause no files to be downloaded; including all files in torrent.')
        else:
            data.options['change']['files_unwanted'] = skip_list
            data.options['change']['files_wanted'] = [x for x in full_list if x not in skip_list]
            log.debug('Downloading %s of %s files in torrent.', len(data.options['change']['files_wanted']),
                      len(full_list))
