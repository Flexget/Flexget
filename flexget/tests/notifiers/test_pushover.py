from __future__ import unicode_literals, division, absolute_import

from time import sleep

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
from flexget.plugin import PluginWarning
from flexget.plugins.notifiers.pushover import PushoverNotifier


@pytest.mark.online
class TestPushoverNotifier(object):
    config = "{tasks:{}}"

    def test_minimal_pushover_config(self, execute_task):
        """
        Test pushover account set using `hirabecicr@throwam.com`, password: `flexget`
        Pushover user key: ua2g3vqjyvqpkyntx19zeruqrn3eim
        Pushover token: aPwSHwkLcNaavShxktBpgJH4bRWc3m
        """
        data2 = {
            'user_key': 'ua2g3vqjyvqpkyntx19zeruqrn3eim',
            'api_key': 'aPwSHwkLcNaavShxktBpgJH4bRWc3m',
            'message': 'test',
            'title': 'test'
        }

        # No exception should be raised
        PushoverNotifier().notify(**data2)

        data1 = {
            'user_key': 'crash',
            'api_key': 'aPwSHwkLcNaavShxktBpgJH4bRWc3m',
            'message': 'test',
            'title': 'test'
        }
        with pytest.raises(PluginWarning):
            PushoverNotifier().notify(**data1)
