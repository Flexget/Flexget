import logging

log = logging.getLogger('btchat')

class ModifyBtChat:

    '''Fixes bt-chat.com urls so that downloading works .. stupid javascript download delay'''

    def register(self, manager, parser):
        manager.register(instance=self, event='input', keyword='btchat',
                         callback=self.run, order=65535, debug_module=False, builtins=True)

    def run(self, feed):
        for entry in feed.entries:
            if entry['url'].startswith('http://www.bt-chat.com/download.php'):
                log.debug('ModifyBtChat fixing download url %s' % entry['url'])
                entry['url'] = entry['url'].replace('download.php', 'download1.php')
                log.debug('ModifyBtChat fixed download url %s' % entry['url'])
        
