from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.plugin import priority, register_plugin
from flexget.utils.log import log_once

log = logging.getLogger('urlfix')


class UrlFix(object):
    """
    Automatically fix broken urls.
    """

    schema = {'type': 'boolean'}

    @priority(-255)
    def on_task_input(self, task):
        if 'urlfix' in task.config:
            if not task.config['urlfix']:
                return
        for entry in task.entries:
            if '&amp;' in entry['url']:
                log_once('Corrected `%s` url (replaced &amp; with &)' % entry['title'], logger=log)
                entry['url'] = entry['url'].replace('&amp;', '&')


register_plugin(UrlFix, 'urlfix', builtin=True)
