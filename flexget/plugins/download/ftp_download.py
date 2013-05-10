import logging
import os
import ftplib
import datetime
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
                tls: False
                ftp_tmp_path: /tmp
    
        TODO:
          - Resume downloads
          - create banlists files
          - validate conections parameters

    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('integer', key='use-ssl')
        root.accept('text', key='ftp_tmp_path')
        return root

    def prepare_config(self, config, task):
        config.setdefault('use-ssl', False)
        temp_path = os.path.join(task.manager.config_base, 'temp')
        config.setdefault('ftp_tmp_path', temp_path)

        return config

    def on_task_download(self, task, config):
        config = self.prepare_config(config, task)
        entries = task.accepted
        for entry in entries:
            ftpUrl = urlparse(entry.get('url'))
            title = entry.get('title')
            
            if config['use-ssl']:
                ftp = ftplib.FTP_TLS()
            else:
                ftp = ftplib.FTP()

            try:
            #ftp.set_debuglevel(2)
                ftp.connect(ftpUrl.hostname, ftpUrl.port)
                ftp.login(ftpUrl.username, ftpUrl.password)
                ftp.sendcmd('TYPE I')
                ftp.set_pasv(True)
            except ftplib.error_perm, ex:
                log.error('Connection error')

            if not os.path.isdir(config['ftp_tmp_path']):
                log.debug('creating base path: %s' % config['ftp_tmp_path'])
                os.mkdir(config['ftp_tmp_path'])
    
            tmp_path = os.path.join(config['ftp_tmp_path'], title)
            log.info('temp path %s' % tmp_path)
            if not os.path.isdir(tmp_path):
                log.debug('creating tmp_path %s' % tmp_path)
                os.mkdir(tmp_path)

            try: # Directory
                ftp.cwd(ftpUrl.path)
                self.ftp_walk(ftp, tmp_path)
            except: # File
                self.ftp_down(ftp, ftpUrl.path, tmp_path)
            
    def ftp_walk(self, ftp, tmp_path):
        log.info("DIR->" + ftp.pwd())
        try:
            dirs = ftp.nlst(ftp.pwd())
        except ftplib.error_perm, ex:
            log.info("Error %s" % ex)
            return

        if not dirs: 
            return

        for item in (path for path in dirs if path not in ('.', '..')):
            log.debug('Item: ' + item)
            base_item_name = os.path.basename(item)
            try:
                ftp.cwd(item)
                log.debug('DIRECTORY: %s' % ftp.pwd())
                new_tmp_dir = os.path.join(tmp_path, base_item_name)

                if not os.path.isdir(new_tmp_dir):
                    os.mkdir(new_tmp_dir)
                    log.info('Creating tmp_path %s' % new_tmp_dir)
        
                self.ftp_walk(ftp, new_tmp_dir)
                ftp.cwd('..')
            except Exception, e:
                log.info("downloading " + base_item_name + " in " + tmp_path)
                self.ftp_down(ftp, item, tmp_path)

    def ftp_down(self, ftp, file_name, tmp_path):
        currdir = os.path.dirname(file_name)
        file_name = os.path.basename(file_name)

        tempdir = tmp_path 
        if not os.path.exists(tempdir): 
            os.makedirs(tempdir)

        src_filesize = 0
        try:
            ftp.voidcmd('TYPE I') # para que el ftp.size funcione correctamente
            src_filesize = ftp.size(file_name)
        except ftplib.error_perm, ex:
            #IS directory! walk
            self.ftp_walk(ftp, tmp_path)

        try:
            dst_file = os.path.join(tempdir, file_name)
            action = 'Download'
            if os.path.exists(dst_file):
                dst_filesize = os.stat(dst_file).st_size
                if src_filesize == dst_filesize:
                    log.info('File ' + file_name + ' completed')
                    action = 'NoDownload'

            if action == 'Download':
                with open(os.path.join(tempdir, file_name), 'wb') as f:
                    def callback(data):
                        f.write(data)
                    ftp.retrbinary('RETR %s' % file_name, callback)
                    f.close()
                    log.info('RETR: ' + os.path.join(tempdir, file_name))
            else:
                log.info('NoDownload: ' + file_name + ' -> ' + os.path.join(tempdir, file_name))
        except Exception, e:
            log.exception(e) 

register_plugin(OutputFtp, 'ftp_download', api_ver=2)
