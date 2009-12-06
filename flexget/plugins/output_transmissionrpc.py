import netrc
import logging
import transmissionrpc
from flexget.plugin import *
from flexget import validator

log = logging.getLogger('transmissionrpc')


class PluginTransmissionrpc:
    """
    Add url from entry url to transmission
     
    Example: transmissionrpc:
               host: localhost
               port: 9091
               netrc: /home/flexget/.tmnetrc
    """

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        advanced = root.accept('dict')
        advanced.accept('text', key='host')
        advanced.accept('number', key='port')
        advanced.accept('file', key='netrc')
        return root

    def on_feed_output(self, feed):
        """ event handler """ 
        if len(feed.accepted) > 0: 
            self.add_to_transmission(feed)

    def add_to_transmission(self, feed):
        """ adds accepted entries to transmission """
        user, account, password = None, None, None
 
        conf = feed.config['transmissionrpc']
   
        if 'netrc' in feed.config['transmissionrpc']:
  
            try:
                user, account, password = netrc.netrc(conf['netrc']).authenticators(conf['host'])
            except IOError, e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError, e:
                log.error('netrc: %s, file: %s, line: %n' % (e.msg, e.filename, e.line))

            cli = transmissionrpc.Client(conf['host'], conf['port'], user, password)

            for entry in feed.accepted:
                if entry['url'].lower().find('magnet:', 0, 7):
                    cli.add(None, filename=entry['url'])
                else:
                    cli.add_url(entry['url'])

register_plugin(PluginTransmissionrpc, 'transmissionrpc')
