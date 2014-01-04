import logging
import ftplib
import os

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
          use-ssl: no
          name: <ftp name>
          username: <username>
          password: <password>
          host: <host to connect>
          port: <port>
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
        config.accept('boolean', key='use-ssl')
        return root

    def prepare_config(self, config):
        config.setdefault('use-ssl', False)
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
            
        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        entries = []
        for path in config['dirs']:
            baseurl = "ftp://%s:%s@%s:%s/" % (connection_config['username'], connection_config['password'],
                                              connection_config['host'], connection_config['port'])

            try:
                dirs = ftp.nlst(path)
            except ftplib.error_perm as e:
                raise plugin.PluginWarning(str(e))

            if not dirs:
                log.verbose('Directory %s is empty', path)

            for p in dirs:
                url = baseurl + p
                title = os.path.basename(p)
                log.info('Accepting entry %s ' % title)
                entries.append(Entry(title, url))

        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(InputFtpList, 'ftp_list', api_ver=2)
