import logging
import os
import ftplib
import re
from urlparse import urlparse
from flexget.entry import Entry
from flexget.plugin import register_plugin

log = logging.getLogger('ftp')


class OutputFtp(object):
    """
        Ftp Download plugin

        input-url: ftp://<user>:<password>@<host>:<port>/<path to file>
        Example: ftp://anonymous:anon@my-ftp-server.com:21/torrent-files-dir

        config:
            ftp_download:
              use-ssl: False
              use-secure: False
              path: /home/dl/tv
              skiplist: \.message|\.diz$|Sample

        TODO:
          - validate connection parameters
    """

    schema = {
        'type': 'object',
        'properties': {
            'use-ssl': {'type': 'boolean', 'default': False},
            'use-secure': {'type': 'boolean', 'default': False},
            'path': {'type': 'string', 'format': 'path', 'Required': 'true'},
            'skiplist': {'type': "string", 'format': 'regexp', 'default': ''}
        },
        'additionalProperties': False
    }

    def on_task_download(self, task, config):
        skipreg = config['skiplist']

        if (len(config['path']) == 0):
            config['path'] = os.path.join(task.manager.config_base, 'temp')

        if (skipreg is not None and len(skipreg) == 0):
            skipreg = None

        if config['use-ssl']:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        for entry in task.accepted:
            ftp_url = urlparse(entry.get('url'))

            title = entry.get('title')
            tmp_path = os.path.join(config['path'], title)
            log.info('download path %s' % tmp_path)
            try:
                # ftp.set_debuglevel(2)
                ftp.connect(ftp_url.hostname, ftp_url.port)
                ftp.login(ftp_url.username, ftp_url.password)
                ftp.sendcmd('TYPE I')
                ftp.set_pasv(True)
            except ftplib.error_perm as ex:
                    log.error('Connection error: %s' % str(ex))
                    continue

            if (config['use-secure']):
                ftp.prot_p()

            try:
                ftp.cwd(ftp_url.path)
                self.ftp_walk(ftp, tmp_path, skipreg)
            except ftplib.error_perm as e:
                if (e.args[0][:3] != '550' or re.search('No such file or directory$', str(e), re.I) is None):
                    log.error('Failed to find ftp-path: %s' % str(e))
                else:
                    # Path is actually a file
                    self.ftp_down(ftp, ftp_url.path, tmp_path, skipreg)
            ftp.close()

    def ftp_walk(self, ftp, tmp_path, skipreg):
        log.debug("DIR->" + ftp.pwd())
        try:
            dirs = ftp.nlst()
        except ftplib.error_perm as ex:
            # Path is empty.
            return

        if (skipreg is not None):
            dirs = (d for d in dirs if (re.search(skipreg, d, re.I) is None))

        for item in (path for path in dirs if path not in ('.', '..')):
            log.debug('Item: ' + item)
            try:
                ftp.cwd(item)
                log.debug('DIRECTORY: %s' % ftp.pwd())

                new_tmp_dir = os.path.join(tmp_path, os.path.basename(item))
                self.ftp_walk(ftp, new_tmp_dir, skipreg)
                ftp.cwd('..')
            except ftplib.error_perm:
                # 550 while CWD, meaning it is a file.
                self.ftp_down(ftp, item, tmp_path)

    def ftp_down(self, ftp, file_name, tmp_path):
        file_name = os.path.basename(file_name)
        dst_file = os.path.join(tmp_path, file_name)
        src_filesize = 0
        dst_filesize = 0
        dl_offset = None

        if not os.path.exists(tmp_path):
            os.makedirs(tmp_path)

        try:
            ftp.voidcmd('TYPE I')  # To make sure ftp.size functions correctly
            src_filesize = ftp.size(file_name)

            fmode = 'wb'
            if os.path.exists(dst_file):
                dst_filesize = os.stat(dst_file).st_size
                if src_filesize <= dst_filesize:
                    log.info('File ' + file_name + ' already downloaded.')
                    return
                elif dst_filesize > 20480:
                    fmode = 'a+b'
                    dl_offset = dst_filesize - 20480  # Rollback 20kb

            if (dl_offset is not None):
                log.info("resuming " + file_name + " in " + tmp_path)
            else:
                log.info("downloading " + file_name + " in " + tmp_path)

            with open(os.path.join(tmp_path, file_name), fmode) as f:
                if (dl_offset is not None):
                    f.seek(dl_offset, 0)
                    f.truncate()
                ftp.retrbinary('RETR %s' % file_name, f.write, 8192, dl_offset)
        except ftplib.error_perm, ex:
            log.error("Unknown error while retr: %s" % str(ex))
        except Exception, e:
            log.exception(e)

register_plugin(OutputFtp, 'ftp_download', api_ver=2)
