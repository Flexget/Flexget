from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse, unquote

import logging
import os
import ftplib
import time

from flexget import plugin
from flexget.event import event
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError

log = logging.getLogger('ftp')


class OutputFtp(object):
    """
        Ftp Download plugin

        input-url: ftp://<user>:<password>@<host>:<port>/<path to file>
        Example: ftp://anonymous:anon@my-ftp-server.com:21/torrent-files-dir

        config:
            ftp_download:
              use-ssl: <True/False>
              ftp_tmp_path: <path>
              delete_origin: <True/False>
              download_empty_dirs: <True/False>

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
            'delete_origin': {'type': 'boolean', 'default': False},
            'download_empty_dirs': {'type': 'boolean', 'default': False},
        },
        'additionalProperties': False,
    }

    def prepare_config(self, config, task):
        config.setdefault('use-ssl', False)
        config.setdefault('delete_origin', False)
        config.setdefault('ftp_tmp_path', os.path.join(task.manager.config_base, 'temp'))
        config.setdefault('download_empty_dirs', False)
        return config

    def ftp_connect(self, config, ftp_url, current_path):
        if config['use-ssl']:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        # ftp.set_debuglevel(2)
        log.debug("Connecting to " + ftp_url.hostname)
        ftp.connect(ftp_url.hostname, ftp_url.port)
        ftp.login(ftp_url.username, ftp_url.password)
        if config['use-ssl']:
            ftp.prot_p()
        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        log.debug("Changing directory to: " + current_path)
        ftp.cwd(current_path)

        return ftp

    def check_connection(self, ftp, config, ftp_url, current_path):
        try:
            ftp.voidcmd("NOOP")
        except (IOError, ftplib.Error):
            ftp = self.ftp_connect(config, ftp_url, current_path)
        return ftp

    def on_task_download(self, task, config):
        config = self.prepare_config(config, task)
        for entry in task.accepted:
            ftp_url = urlparse(entry.get('url'))
            ftp_url = ftp_url._replace(path=unquote(ftp_url.path))
            current_path = os.path.dirname(ftp_url.path)
            try:
                ftp = self.ftp_connect(config, ftp_url, current_path)
            except ftplib.all_errors as e:
                entry.fail("Unable to connect to server : %s" % (e))
                break

            to_path = config['ftp_tmp_path']

            try:
                to_path = entry.render(to_path)
            except RenderError as err:
                raise plugin.PluginError(
                    "Path value replacement `%s` failed: %s" % (to_path, err.args[0])
                )

            # Clean invalid characters with pathscrub plugin
            to_path = pathscrub(to_path)

            if not os.path.exists(to_path):
                log.debug("Creating base path: %s" % to_path)
                os.makedirs(to_path)
            if not os.path.isdir(to_path):
                raise plugin.PluginWarning("Destination `%s` is not a directory." % to_path)

            file_name = os.path.basename(ftp_url.path)

            try:
                # Directory
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd(file_name)
                self.ftp_walk(ftp, os.path.join(to_path, file_name), config, ftp_url, ftp_url.path)
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd('..')
                if config['delete_origin']:
                    ftp.rmd(file_name)
            except ftplib.error_perm:
                # File
                self.ftp_down(ftp, file_name, to_path, config, ftp_url, current_path)

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
            if config['download_empty_dirs']:
                os.mkdir(tmp_path)
            else:
                log.debug("Empty directory, skipping.")
            return ftp

        for file_name in (path for path in dirs if path not in ('.', '..')):
            file_name = os.path.basename(file_name)
            try:
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd(file_name)
                if not os.path.isdir(tmp_path):
                    os.mkdir(tmp_path)
                    log.debug("Directory %s created" % tmp_path)
                ftp = self.ftp_walk(
                    ftp,
                    os.path.join(tmp_path, os.path.basename(file_name)),
                    config,
                    ftp_url,
                    os.path.join(current_path, os.path.basename(file_name)),
                )
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd('..')
                if config['delete_origin']:
                    ftp.rmd(os.path.basename(file_name))
            except ftplib.error_perm:
                ftp = self.ftp_down(
                    ftp, os.path.basename(file_name), tmp_path, config, ftp_url, current_path
                )
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
        except Exception:
            file_size = 1

        max_attempts = 5
        size_at_last_err = 0
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
                    if size_at_last_err == local_file.tell():
                        # Nothing new was downloaded so the error is most likely connected to the resume functionality.
                        # Delete the downloaded file and try again from the beginning.
                        local_file.close()
                        os.remove(os.path.join(tmp_path, file_name))
                        local_file = open(os.path.join(tmp_path, file_name), 'a+b')
                        max_attempts -= 1

                    size_at_last_err = local_file.tell()
                    log.debug("Retrying download after error %s" % error.args[0])
                    # Short timeout before retry.
                    time.sleep(1)
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
