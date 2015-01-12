import logging
import os
import ftplib
from urlparse import urlparse

from flexget import plugin
from flexget.event import event

log = logging.getLogger('ftp')


class OutputFtp(object):
    """
        Ftp Download plugin

        input-url: ftp://<user>:<password>@<host>:<port>/<path to file>
        Example: ftp://anonymous:anon@my-ftp-server.com:21/torrent-files-dir

        config:
            ftp_download:
              tls: False
              ftp_tmp_path: /tmp

        TODO:
          - Resume downloads
          - create banlists files
          - validate connection parameters

    """

    schema = {
        'type': 'object',
        'properties': {
            'use-ssl': {'type': 'boolean', 'default': False},
            'ftp_tmp_path': {'type': 'string', 'format': 'path'},
            'delete_origin': {'type': 'boolean', 'default' : False}
        },
        'additionalProperties': False
    }

    def prepare_config(self, config, task):
        config.setdefault('use-ssl', False)
        config.setdefault('delete_origin', False)
        config.setdefault('ftp_tmp_path', os.path.join(task.manager.config_base, 'temp'))
        return config

    def ftp_connect(self, config, ftp_url, current_path):
        if config['use-ssl']:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()
        log.debug("Connecting to " + ftp_url.hostname)
        ftp.connect(ftp_url.hostname, ftp_url.port)
        ftp.login(ftp_url.username, ftp_url.password)
        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        ftp.cwd(current_path)

        return ftp

    def check_connection(self, ftp, config, ftp_url, current_path):
        try:
            ftp.voidcmd("NOOP")
        except:
            ftp = self.ftp_connect(config, ftp_url, current_path)
        return ftp

    def on_task_download(self, task, config):
        config = self.prepare_config(config, task)
        for entry in task.accepted:
            ftp_url = urlparse(entry.get('url'))
            current_path = os.path.dirname(ftp_url.path)
            try:
                ftp = self.ftp_connect(config, ftp_url, current_path)
            except:
                entry.failed("Unable to connect to server")
                break

            if not os.path.isdir(config['ftp_tmp_path']):
                log.debug('creating base path: %s' % config['ftp_tmp_path'])
                os.mkdir(config['ftp_tmp_path'])

            file_name = os.path.basename(ftp_url.path)

            try:
                # Directory
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd(file_name)
                self.ftp_walk(ftp, os.path.join(config['ftp_tmp_path'], file_name), config, ftp_url, ftp_url.path)
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd('..')
                if config['delete_origin']:
                    ftp.rmd(file_name)
            except ftplib.error_perm:
                # File
                self.ftp_down(ftp, file_name, config['ftp_tmp_path'], config, ftp_url, current_path)

            ftp.close()

    def on_task_output(self, task, config):
        """Count this as an output plugin."""

    def ftp_walk(self, ftp, tmp_path, config, ftp_url, current_path):
        log.debug("DIR->" + ftp.pwd())
        log.debug("FTP tmp_path : " + tmp_path)
        try:
            ftp = self.check_connection(ftp, config, ftp_url, current_path)
            dirs = ftp.nlst(ftp.pwd())
        except ftplib.error_perm as ex:
            log.info("Error %s" % ex)
            return ftp

        if not dirs:
            return ftp

        for file_name in (path for path in dirs if path not in ('.', '..')):
            file_name = os.path.basename(file_name)
            try:
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd(file_name)
                if not os.path.isdir(tmp_path):
                    os.mkdir(tmp_path)
                    log.debug("Directory %s created" % tmp_path)
                ftp = self.ftp_walk(ftp,
                                    os.path.join(tmp_path, os.path.basename(file_name)),
                                    config,
                                    ftp_url,
                                    os.path.join(current_path, os.path.basename(file_name)))
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd('..')
                if config['delete_origin']:
                    ftp.rmd(os.path.basename(file_name))
            except ftplib.error_perm:
                ftp = self.ftp_down(ftp, os.path.basename(file_name), tmp_path, config, ftp_url, current_path)
        ftp = self.check_connection(ftp, config, ftp_url, current_path)
        return ftp

    def ftp_down(self, ftp, file_name, tmp_path, config, ftp_url, current_path):
        log.debug("Downloading %s into %s" % (file_name, tmp_path))

        if not os.path.exists(tmp_path):
            os.makedirs(tmp_path)

        local_file = open(os.path.join(tmp_path, file_name), 'a+b')
        ftp = self.check_connection(ftp, config, ftp_url, current_path)
        try:
            ftp.sendcmd("TYPE I")
            file_size = ftp.size(file_name)
        except Exception as e:
            file_size = 1

        max_attempts = 5

        log.info("Starting download of %s into %s" % (file_name, tmp_path))

        while file_size > local_file.tell():
            try:
                if local_file.tell() != 0:
                    ftp = self.check_connection(ftp, config, ftp_url, current_path)
                    ftp.retrbinary('RETR %s' % file_name, local_file.write, local_file.tell())
                else:
                    ftp = self.check_connection(ftp, config, ftp_url, current_path)
                    ftp.retrbinary('RETR %s' % file_name, local_file.write)
            except Exception as error:
                if max_attempts != 0:
                    log.debug("Retrying download after error %s" % error);
                else:
                    log.error("Too many errors downloading %s. Aborting." % file_name)
                    break

        local_file.close()
        if config['delete_origin']:
            ftp = self.check_connection(ftp, config, ftp_url, current_path)
            ftp.delete(file_name)

        return ftp


@event('plugin.register')
def register_plugin():
    plugin.register(OutputFtp, 'ftp_download', api_ver=2)
