from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from requests.packages import urllib3

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
            # Disabling verification results in a warning for every HTTPS
            # request:
            # "InsecureRequestWarning: Unverified HTTPS request is being made.
            #  Adding certificate verification is strongly advised. See:
            #  https://urllib3.readthedocs.io/en/latest/security.html"
            # Disable those warnings because the user has explicitly disabled
            # verification and the warning is not beneficial.
            # This change is permanent rather than task scoped, but there won't
            # be any warnings to disable when verification is enabled.
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@event('plugin.register')
def register_plugin():
    plugin.register(VerifySSLCertificates, 'verify_ssl_certificates', api_ver=2)
