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
        advanced.accept('decimal', key='ratio', required=False) 
        return root

    def on_process_start(self, feed):
        '''event handler'''
        set_plugin = get_plugin_by_name('set')
        
        set_plugin.instance.register_keys({'path': 'path', \
                                           'addpaused': 'boolean', \
                                           'maxconnections': 'number', \
                                           'maxupspeed': 'number',  \
                                           'maxdownspeed': 'number', \
                                           'ratio': 'decimal'})

    def on_feed_output(self, feed):
        """ event handler """ 
        if len(feed.accepted) > 0: 
            self.add_to_transmission(feed)
    
    def _make_torrent_options_dict(self, feed, entry):

        opt_dic = {}

        for opt_key in \
        ['path', 'addpaused', 'maxconnections', 'maxupspeed', 'maxdownspeed', 'ratio']:
            if opt_key in entry:
                opt_dic[opt_key] = entry[opt_key]
            elif opt_key in feed.config['transmissionrpc']:
                opt_dic[opt_key] = feed.config['transmissionrpc'][opt_key]

        options = {}
        options['add'] = {}
        options['change'] = {}

        if 'path' in opt_dic:
            options['add']['download_dir'] = opt_dic['path']
        if 'addpaused' in opt_dic and opt_dic['addpaused']: 
            options['add']['paused'] = True
        if 'maxconnections' in opt_dic:
            options['add']['peer_limit'] = opt_dic['maxconnections']

        if 'maxupspeed' in opt_dic:
            options['change']['uploadLimit'] = opt_dic['maxupspeed']
            options['change']['uploadLimited'] = True
        if 'maxdownspeed' in opt_dic:
            options['change']['downloadLimit'] = opt_dic['maxdownspeed']
            options['change']['downloadLimited'] = True

        if 'ratio' in opt_dic:
            options['change']['seedRatioLimit'] = opt_dic['ratio']
            if opt_dic['ratio'] == 0.0:
                '''
                seedRatioMode:
                0 follow the global settings
                1 override the global settings, seeding until a certain ratio
                2 override the global settings, seeding regardless of ratio
                '''
                options['change']['seedRatioMode'] = 3
            else:
                options['change']['seedRatioMode'] = 2

        return options

    def add_to_transmission(self, feed):
        """ adds accepted entries to transmission """
        try:
            import transmissionrpc
            from transmissionrpc.transmission import TransmissionError
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

            options = self._make_torrent_options_dict(feed, entry)
            
            try:
                r = cli.add(None, 30, filename=entry['url'], **options['add'])
            except TransmissionError, e:
                log.error(e.message)

            if len(options['change'].keys()) > 0:
                for id in r.keys():
                    cli.change(id, 30, **options['change'])

register_plugin(PluginTransmissionrpc, 'transmissionrpc')
