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
                temp_down: /tmp  
                tls: 0 
    
        TODO:
          - Resume downloads
          - create banlists files
          - validate conections parameters

    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('integer', key='use-ssl')
        return root

    def prepare_config(self, config):
        config.setdefault('use-ssl', False)
        return config

    def on_task_download(self, task, config):
        config = self.prepare_config(config)
        entries = task.accepted
        for entry in entries:
            ftpUrl = urlparse(entry.get('url'))
            title = entry.get('title')
            
            if config['use-ssl']:
                ftp = ftplib.FTP_TLS()
            else:
                ftp = ftplib.FTP()

            #ftp.set_debuglevel(2)
            ftp.connect(ftpUrl.hostname, ftpUrl.port)
            ftp.login(ftpUrl.username, ftpUrl.password)
            ftp.sendcmd('TYPE I')
            ftp.set_pasv(True)
    
            #tmp_path = os.path.join(config['temp'], title);
            tmp_path = os.path.join(entry.get("temp_down"), title)
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
        try: 
            dirs = ftp.nlst(ftp.pwd())
        except: 
            return

        if not dirs: 
            return

        for item in (path for path in dirs if path not in ('.', '..')):
            try:
                ftp.cwd(item)
                log.info('DIR: %s' % ftp.pwd())
                self.ftp_walk(ftp, tmp_path)
                ftp.cwd('..')
            except Exception, e:
                self.ftp_down(ftp, item, tmp_path)

    def ftp_down(self, ftp, fName, tmp_path):
        currdir = os.path.dirname(fName)
        fileName = os.path.basename(fName)
        tmpDir = tmp_path # + "/" + currdir #os.path.join(tmp_path, currdir)
        if not os.path.exists(tmpDir): 
            os.makedirs(tmpDir)
        try:
            ftp.voidcmd('TYPE I') # para que el ftp.size funcione correctamente
            tamSrc = ftp.size(fileName)
            dstFile = os.path.join(tmpDir, fileName)
            action = 'Download'
            if os.path.exists(dstFile):
                tamDst = os.stat(dstFile).st_size
                if tamSrc == tamDst:
                    action = 'NoDownload'

            if action == 'Download':
                with open(os.path.join(tmpDir, fileName), 'wb') as f:
                    def callback(data):
                        f.write(data)
                    ftp.retrbinary('RETR %s' % fileName, callback)
                    f.close()
                    log.info('RETR: ' + os.path.join(tmpDir, fileName))
            else:
                log.info('NoDownload: ' + os.path.join(tmpDir, fileName))
        except Exception, e:
            print e

register_plugin(OutputFtp, 'ftp_download', api_ver=2)
