import logging
from flexget.plugin import *
from flexget.utils.log import log_once

log = logging.getLogger('urlfix')


class UrlFix(object):
    """
    Automatically fix broken urls.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(-255)
    def on_feed_input(self, feed):
        if 'urlfix' in feed.config:
            if not feed.config['urlfix']:
                return
        for entry in feed.entries:
            if '&amp;' in entry['url']:
                log_once('Corrected `%s` url (replaced &amp; with &)' % entry['title'], logger=log)
                entry['url'] = entry['url'].replace('&amp;', '&')


register_plugin(UrlFix, 'urlfix', builtin=True)
