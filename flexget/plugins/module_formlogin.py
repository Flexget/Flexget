import logging
from flexget.feed import Entry
from flexget.plugin import *
import urllib2

log = logging.getLogger('formlogin')


class InputFormLogin(object):
    """
    Login on form
    """

    def on_feed_start(self, feed):
        try:
            from mechanize import Browser
        except ImportError:
            raise PluginError('mechanize module required.', log)
        url = feed.config['form']['url']
        username = feed.config['form']['username']
        password = feed.config['form']['password']

        br = Browser()
        br.set_handle_robots(False)
        br.open(url)

        #br.set_debug_redirects(True)
        #br.set_debug_responses(True)
        #br.set_debug_http(True)

        for form in br.forms():
            loginform = form

        loginform['username'] = username
        loginform['password'] = password

        br.form = loginform

        br.submit()

        cookiejar = br._ua_handlers["_cookies"].cookiejar

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
        urllib2.install_opener(opener)                                

register_plugin(InputFormLogin, 'form')
