import logging
from flexget.plugin import *

log = logging.getLogger('sabnzbd')

class OutputSabnzbd:
    """
        Example:
        
        sabnzbd:
          apikey: 123456
          url: http://localhost/sabnzbd/api?
          category: movies
          
        Note: url has default value of 'http://localhost:8080/sabnzbd/api?'
          
        All parameters:
        
        sabnzbd:
          apikey: ...
          url: ...
          category: ...
          script: ...
          pp: ...
    """
    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='key', required=True)
        config.accept('url', key='url')
        config.accept('text', key='category')
        config.accept('text', key='script')
        config.accept('text', key='pp')
        config.accept('text', key='password')
        config.accept('text', key='username')
        return config

    def get_params(self, config):
        params = {}
        if 'key' in config:
            params['apikey'] = config['key']
        if 'category' in config:
            params['cat'] = '%s' % config['category']
        if 'script' in config:
            params['script'] = config['script']
        if 'pp' in config:
            params['pp'] = config['pp']
        if 'username' in config:
            params['ma_username'] = config['username']
        if 'password' in config:
            params['ma_password'] = config['password']
        params['mode'] = 'addurl'
        return params

    def on_process_start(self, feed):
        """
        register the usable set: keywords
        """
        set = get_plugin_by_name('set')
        set.instance.register_keys({'category':'text'})

    def on_feed_output(self, feed):
        import urllib
        import urllib2
        
        # convert config into url parameters
        config = feed.config['sabnzbd']
        baseurl = config.get('url', 'http://localhost:8080/sabnzbd/api?')
        
        for entry in feed.accepted:
            params = self.get_params(config)
            # allow overriding the category
            if 'category' in entry:
                params['cat'] = entry['category']
            params['name'] = entry['url']
            request_url = baseurl + urllib.urlencode(params)
            log.debug('request_url: %s' % request_url)

            try:            
                response = urllib2.urlopen(request_url).read()
            except:
                log.critical('Failed to use sabnzbd at %s' % request_url)
                feed.fail(entry, 'sabnzbd unreachable')
                continue
            
            if response.lower().find('error') != -1:
                feed.fail(entry, response.replace('\n', ''))
            

register_plugin(OutputSabnzbd, 'sabnzbd')