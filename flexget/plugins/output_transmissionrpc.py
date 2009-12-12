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
        path: the download location
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
        advanced.accept('path', key='path', required=False) 
        advanced.accept('boolean', key='addpaused', required=False) 
        advanced.accept('number', key='maxconnections', required=False) 
        advanced.accept('number', key='maxupspeed', required=False) 
        advanced.accept('number', key='maxdownspeed', required=False) 
        return root

    def on_feed_output(self, feed):
        """ event handler """ 
        if len(feed.accepted) > 0: 
            self.add_to_transmission(feed)
    
    def _options(self, feed):
        options = {}
        options['add'] = {}
        options['change'] = {}

        conf = feed.config['transmissionrpc']
        
        if 'path' in conf:
            options['add']['download_dir'] = conf['path']
        if 'addpaused' in conf and conf['addpaused'] == 'yes': 
            options['add']['paused'] = True
        if 'maxconnections' in conf:
            options['add']['peer_limit'] = conf['maxconnections']

        if 'maxupspeed' in conf:
            options['change']['uploadLimit'] = conf['maxupspeed']
        if 'maxdownspeed' in conf:
            options['change']['downloadLimit'] = conf['maxdownspeed']
        
        return options

    def add_to_transmission(self, feed):
        """ adds accepted entries to transmission """
        try:
            import transmissionrpc
        except:
            raise PluginError('Transmissionrpc module required.', log)
            
        conf = feed.config['transmissionrpc']

        options = self._options(feed)

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
            r = cli.add(None, 30, filename=entry['url'], **options['add'])
            
            if len(options['change'].keys()) > 0:
                for id in r.keys():
                    cli.change(id, 30, **options['change'])

register_plugin(PluginTransmissionrpc, 'transmissionrpc')
