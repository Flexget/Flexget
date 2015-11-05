import logging
import ftplib
import os
import re

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.config_schema import one_or_more

log = logging.getLogger('ftp_list')


class InputFtpList(object):
    """
    Generate entries from a ftp listing

    Configuration:
      ftp_list:
        config:
          name: <ftp name>
          username: <username>
          password: <password>
          host: <host to connect>
          port: <port>
          use-ssl: <yes/no>
          encoding: <auto/utf8/ascii>
          files-only: <yes/no>
          recursive: <yes/no>
          get-size: <yes/no>
        dirs:
          - <directory 1>
          - <directory 2>
          - ....
    """
    encodings = ['auto', 'utf8', 'ascii']
    schema = {
        'type': 'object',
        'properties': {
            'config': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'use-ssl': {'type': 'boolean', 'default': False},
                    'encoding': {'type': 'string', 'enum': encodings, 'default': 'auto'},
                    'files-only': {'type': 'boolean', 'default': False},
                    'recursive': {'type': 'boolean', 'default': False},
                    'get-size': {'type': 'boolean', 'default': True}
                },
                'additionProperties': False,
                'required': ['name', 'username', 'password', 'host', 'port'],
            },
            'dirs': one_or_more({'type': 'string'}),
        },
        'required': ['config'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        connection_config = config['config']

        if connection_config['use-ssl']:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        # ftp.set_debuglevel(2)
        log.debug('Trying connecting to: %s', (connection_config['host']))
        try:
            ftp.connect(connection_config['host'], connection_config['port'])
            ftp.login(connection_config['username'], connection_config['password'])
        except ftplib.all_errors as e:
            raise plugin.PluginError(e)

        log.debug('Connected.')

        encoding = connection_config['encoding']
        files_only = connection_config['files-only']
        recursive = connection_config['recursive']
        get_size = connection_config['get-size']
        mlst_supported = False

        feat_response = ftp.sendcmd('FEAT').splitlines()
        supported_extensions = [feat_item.strip().upper() for feat_item in feat_response[1:len(feat_response) - 1]]

        if encoding.lower() == 'auto' and 'UTF8' in supported_extensions:
            encoding = 'utf8'
        else:
            encoding = 'ascii'

        for supported_extension in supported_extensions:
            if supported_extension.startswith('MLST'):
                mlst_supported = True
                break

        if not mlst_supported:
            log.warning('MLST Command is not supported by the FTP server %s@%s:%s', connection_config['username'],
                        connection_config['host'], connection_config['port'])

        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        entries = []

        for path in config['dirs']:
            baseurl = "ftp://%s:%s@%s:%s/" % (connection_config['username'], connection_config['password'],
                                              connection_config['host'], connection_config['port'])

            self._handle_path(entries, ftp, baseurl, path, mlst_supported, files_only, recursive, get_size, encoding)

        return entries

    def _handle_path(self, entries, ftp, baseurl, path='', mlst_supported=False, files_only=False, recursive=False,
                     get_size=True, encoding=None):
        dirs = self.list_directory(ftp, path)

        for p in dirs:
            if encoding:
                p = p.decode(encoding)

            # Clean file list when subdirectories are used
            p = p.replace(path + '/', '')

            mlst = {}
            if mlst_supported:
                mlst_output = ftp.sendcmd('MLST ' + path + '/' + p)
                clean_mlst_output = [line.strip().lower() for line in mlst_output.splitlines()][1]
                mlst = self.parse_mlst(clean_mlst_output)
            else:
                element_is_directory = self.is_directory(ftp, path + '/' + p)
                if element_is_directory:
                    mlst['type'] = 'dir'
                    log.debug('%s is a directory', p)
                else:
                    mlst['type'] = 'file'
                    log.debug('%s is a file', p)

            if recursive and mlst.get('type') == 'dir':
                self._handle_path(entries, ftp, baseurl, path + '/' + p, mlst_supported, files_only,
                                  recursive, get_size, encoding)

            if not files_only or mlst.get('type') == 'file':
                url = baseurl + path + '/' + p
                url = url.replace(' ', '%20')
                title = os.path.basename(p)
                log.info('Accepting entry "%s" [%s]' % (path + '/' + p, mlst.get('type') or "unknown",))
                entry = Entry(title, url)
                if get_size and 'size' not in mlst:
                    if mlst.get('type') == 'file':
                        entry['content_size'] = ftp.size(path + '/' + p) / (1024 * 1024)
                        log.debug('(FILE) Size = %s', entry['content_size'])
                    elif mlst.get('type') == 'dir':
                        entry['content_size'] = self.get_folder_size(ftp, path, p)
                        log.debug('(DIR) Size = %s', entry['content_size'])
                elif get_size:
                    entry['content_size'] = float(mlst.get('size')) / (1024 * 1024)
                entries.append(entry)
        
    def parse_mlst(self, mlst):
        re_results = re.findall('(.*?)=(.*?);', mlst)
        parsed = {}
        for k, v in re_results:
            parsed[k] = v
        return parsed

    def is_directory(self, ftp, elementpath):
        try:
            original_wd = ftp.pwd()
            ftp.cwd(elementpath)
            ftp.cwd(original_wd)
            return True
        except ftplib.error_perm:
            return False

    def list_directory(self, ftp, path):
        try:
            dirs = ftp.nlst(path)
        except ftplib.error_perm as e:
            # ftp returns 550 on empty dirs
            if str(e).startswith('550 '):
                log.debug('Directory %s is empty.', path)
                dirs = []
            else:
                raise plugin.PluginError(e)
        return dirs

    def get_folder_size(self, ftp, path, p):
        size = 0
        dirs = self.list_directory(ftp, path + '/' + p)

        for filename in dirs:
            filename = filename.replace(path + '/' + p + '/', '')
            try:
                size += ftp.size(path + '/' + p + '/' + filename) / (1024 * 1024)
            except ftplib.error_perm:
                size += self.get_folder_size(ftp, path + '/' + p, filename)
        return size


@event('plugin.register')
def register_plugin():
    plugin.register(InputFtpList, 'ftp_list', api_ver=2)
