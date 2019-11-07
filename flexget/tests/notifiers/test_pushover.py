import pytest

from flexget.components.notify.notifiers.pushover import PushoverNotifier
from flexget.plugin import PluginWarning


@pytest.mark.online
class TestPushoverNotifier:
    config = "{tasks:{}}"

    def test_minimal_pushover_config(self, execute_task):
        """
        Test pushover account set using `hirabecicr@throwam.com`, password: `flexget`
        Pushover user key: ua2g3vqjyvqpkyntx19zeruqrn3eim
        Pushover token: aPwSHwkLcNaavShxktBpgJH4bRWc3m
        """
        config2 = {
            'user_key': 'ua2g3vqjyvqpkyntx19zeruqrn3eim',
            'api_key': 'aPwSHwkLcNaavShxktBpgJH4bRWc3m',
        }

        # No exception should be raised
        PushoverNotifier().notify('test', 'test', config2)

        config1 = {'user_key': 'crash', 'api_key': 'aPwSHwkLcNaavShxktBpgJH4bRWc3m'}
        with pytest.raises(PluginWarning):
            PushoverNotifier().notify('test', 'test', config1)
