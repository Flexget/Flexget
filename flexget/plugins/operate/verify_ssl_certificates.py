from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('verify_ssl')


class VerifySSLCertificates(object):
    """
    Plugin that can off SSL certificate verification.

    Example::
      verify_ssl_certificates: no
    """

    schema = {'type': 'boolean'}

    @plugin.priority(253)
    def on_task_start(self, task, config):
        if config is False:
            task.requests.verify = False


@event('plugin.register')
def register_plugin():
    plugin.register(VerifySSLCertificates, 'verify_ssl_certificates', api_ver=2)
