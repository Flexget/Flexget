import logging
import ftplib
import os
from flexget.entry import Entry
from flexget.plugin import register_plugin, PluginError, PluginWarning

log = logging.getLogger('ftp_list')


class InputFtpList(object):
    """
    Generate entries from a ftp listing

    Configuration:
      ftp_list:
        config:
            use-ssl: 0
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
        config.accept('integer', key='use-ssl')

        return root

    def on_task_input(self, task, config):
        if config['config']['use-ssl'] == 1:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        #ftp.set_debuglevel(2)
        log.debug('Trying connecting to: %s', (config['config']['host']))
        try: 
            ftp.connect(config['config']['host'], config['config']['port'])
            ftp.login(config['config']['username'], config['config']['password'])
        except ftplib.all_errors, e:
            raise PluginError(e)

        log.debug('Connected.')
            
        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        entries = []
        for path in config['dirs']:
            baseurl = "ftp://%s:%s@%s:%s/" % (config['config']['username'], config['config']['password'], 
                      config['config']['host'], config['config']['port']) 

            try:
                dirs = ftp.nlst(path)
            except ftplib.error_perm, e:
                raise PluginWarning(str(e))

            if not dirs:
                log.info('Directory %s is empty', path)

            for p in dirs:
                url = baseurl + p
                title = os.path.basename(p)
                entry = Entry()
                entry['title'] = title
                entry['description'] = title
                entry['url'] = url
                entries.append(entry)

        return entries

register_plugin(InputFtpList, 'ftp_list', api_ver=2)
