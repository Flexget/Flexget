import logging
import ftplib
import os
import re

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

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
        dirs:
          - <directory 1>
          - <directory 2>
          - ....
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('list', key='dirs').accept('text')
        config = root.accept('dict', key='config', required=True)
        config.accept('text', key='name', required=True)
        config.accept('text', key='username', required=True)
        config.accept('text', key='password', required=True)
        config.accept('text', key='host', required=True)
        config.accept('integer', key='port', required=True)
        config.accept('text', key='encoding')
        config.accept('boolean', key='files-only')
        config.accept('boolean', key='recursive')
        config.accept('boolean', key='use-ssl')
        return root

    def prepare_config(self, config):
        config['config'].setdefault('use-ssl', False)
        config['config'].setdefault('encoding', 'auto')
        config['config'].setdefault('files-only', False)
        config['config'].setdefault('recursive', False)
        config.setdefault('dirs', [""])
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
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
        mlst_supported = False

        feat_response = ftp.sendcmd('FEAT').splitlines()
        supported_extensions = [feat_item.strip().upper() for feat_item in feat_response[1:len(feat_response)-1]]

        if encoding.lower() == 'auto' and 'UTF8' in supported_extensions:
            encoding = 'utf8'
        else:
            encoding = 'ascii'

        for supported_extension in supported_extensions:
            if supported_extension.startswith('MLST'):
                mlst_supported = True
                break

        if not mlst_supported:
            log.warning('MLST Command is not supported by the FTP server %s@%s:%s', connection_config['username'], connection_config['host'], connection_config['port'])

        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        entries = []

        for path in config['dirs']:
            baseurl = "ftp://%s:%s@%s:%s/" % (connection_config['username'], connection_config['password'],
                                              connection_config['host'], connection_config['port'])

            self._handle_path(entries, ftp, baseurl, path, mlst_supported, files_only, recursive, encoding)

        return entries

    def _handle_path(self, entries, ftp, baseurl, path='', mlst_supported=False, files_only=False, recursive=False, encoding=None):
        try:
            dirs = ftp.nlst(path)
        except ftplib.error_perm as e:
            raise plugin.PluginWarning(str(e))

        if not dirs:
            log.verbose('Directory %s is empty', path)

        if len(dirs) == 1 and path == dirs[0]:
            # It's probably a file
            return False

        for p in dirs:
            if encoding:
                p = p.decode(encoding)

            mlst = {}
            if mlst_supported:
                mlst_output = ftp.sendcmd('MLST ' + path + '/' + p)
                clean_mlst_output = [line.strip().lower() for line in mlst_output.splitlines()][1]
                mlst = self.parse_mlst(clean_mlst_output)

            if recursive and (not mlst_supported or mlst.get('type') == 'dir'):
                is_directory = self._handle_path(entries, ftp, baseurl, path + '/' + p, mlst_supported, files_only, recursive, encoding)
                if not is_directory and not mlst_supported:
                    mlst['type'] = 'file'

            if not files_only or mlst.get('type') == 'file':
                url = baseurl + p
                title = os.path.basename(p)
                log.info('[%s] "%s"' % (mlst.get('type') or "unknown", path + '/' + p,))
                entry = Entry(title, url)
                if not 'size' in mlst:
                    entry['content-size'] = ftp.size(path + '/' + p) / (1024 * 1024)
                else:
                    entry['content-size'] = float(mlst.get('size')) / (1024 * 1024)
                entries.append(entry)

        return True

    def parse_mlst(self, mlst):
        re_results = re.findall('(.*?)=(.*?);', mlst)
        parsed = {}
        for k, v in re_results:
            parsed[k] = v
        return parsed


@event('plugin.register')
def register_plugin():
    plugin.register(InputFtpList, 'ftp_list', api_ver=2)
