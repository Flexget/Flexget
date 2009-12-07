from netrc import netrc, NetrcParseError
import logging
from flexget.plugin import *
from flexget import validator

log = logging.getLogger('transmissionrpc')


class PluginTransmissionrpc:
    """
      Add url from entry url to transmission
     
      Example: 
    
      transmissionrpc:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
    """

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        advanced = root.accept('dict')
        advanced.accept('text', key='host', required=True)
        advanced.accept('number', key='port', required=True)
        """note that password is optional in transmission"""
        advanced.accept('file', key='netrc', required=False) 
        advanced.accept('text', key='username', required=False) 
        advanced.accept('text', key='password', required=False) 
        return root

    def on_feed_output(self, feed):
        """ event handler """ 
        if len(feed.accepted) > 0: 
            self.add_to_transmission(feed)

    def add_to_transmission(self, feed):
        """ adds accepted entries to transmission """
        try:
            import transmissionrpc
        except:
            raise PluginError('Transmissionrpc module required.', log)
            
        conf = feed.config['transmissionrpc']

        user, password = None, None

        if 'netrc' in conf:
  
            try:
                user, account, password = netrc(conf['netrc']).authenticators(conf['host'])
            except IOError, e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError, e:
                log.error('netrc: %s, file: %s, line: %n' % (e.msg, e.filename, e.line))
       
        else:

            if 'username' in conf: 
                user = conf['username']
            if 'password' in conf: 
                password = conf['password']

        cli = transmissionrpc.Client(conf['host'], conf['port'], user, password)

        for entry in feed.accepted:
            if entry['url'].lower().find('magnet:', 0, 7):
                cli.add(None, filename=entry['url'])
            else:
                cli.add_url(entry['url'])

register_plugin(PluginTransmissionrpc, 'transmissionrpc')
