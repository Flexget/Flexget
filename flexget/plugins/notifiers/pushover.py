from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

import datetime
import requests

from flexget.notifier import Notifier
from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError

log = logging.getLogger('pushover')

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
NUMBER_OF_RETRIES = 3


class Pushover(Notifier):
    def __init__(self, task, scope, iterate_on, test, config):
        super(Pushover, self).__init__(task, scope, iterate_on, test)
        self.config = self.prepare_config(config)

    defaults = {
        'message': '{% if series_name is defined %}'
                   '{{tvdb_series_name|d(series_name)}} '
                   '{{series_id}} {{tvdb_ep_name|d('')}}'
                   '{% elif imdb_name is defined %}'
                   '{{imdb_name}} {{imdb_year}}'
                   '{% else %}'
                   '{{title}}'
                   '{% endif %}',
        'url': '{% if imdb_url is defined %}{{imdb_url}}{% endif %}',
        'title': '{{task}}'
    }

    last_request = datetime.datetime.strptime('2000-01-01', '%Y-%m-%d')

    def pushover_request(self, data):
        time_dif = (datetime.datetime.now() - self.last_request).seconds

        # Require at least 5 seconds of waiting between API calls
        while time_dif < 5:
            time_dif = (datetime.datetime.now() - self.last_request).seconds
        try:
            response = requests.post(PUSHOVER_URL, data=data)
            self.last_request = datetime.datetime.now()
        except RequestException:
            raise
        return response

    def prepare_config(self, config):
        """
        Returns prepared config with Flexget default values
        :param config: User config
        :return: Config with defaults
        """
        config = config
        if not isinstance(config['userkey'], list):
            config['userkey'] = [config['userkey']]
        config.setdefault('message', self.defaults['message'])
        config.setdefault('title', self.defaults['title'])
        config.setdefault('url', self.defaults['url'])

        return config

    def notify(self):
        if not self.iterate_on:
            log.debug('did not have any entities to iterate on')
            return

        data = {'token': self.config['apikey']}
        # Loop through the provided entities
        for entry in self.iterate_on:
            for key, value in list(self.config.items()):
                if key in ['apikey', 'userkey']:
                    continue

                # Special case for html key
                if key == 'html' and value is True:
                    data['html'] = 1
                    continue

                # Tried to render data in field
                try:
                    data[key] = entry.render(value)
                except RenderError as e:
                    log.warning('Problem rendering {0}: {1}'.format(key, e))
                    data[key] = None
                except ValueError:
                    data[key] = None

                # If field is empty or rendering fails, try to render field default if exists
                if not data[key]:
                    try:
                        data[key] = entry.render(self.defaults.get(key))
                    except ValueError:
                        if value:
                            data[key] = value

            # Special case, verify certain fields exists if priority is 2
            if data.get('priority') == 2 and not all([data.get('expire'), data.get('retry')]):
                log.warning('Priority set to 2 but fields "expire" and "retry" are not both present.'
                            ' Lowering priority to 1')
                data['priority'] = 1

            for userkey in self.config['userkey']:
                # Build the request
                data['user'] = userkey

                # Check for test mode
                if self.test:
                    log.info('Test mode.  Pushover notification would be:')
                    for key, value in list(data.items()):
                        log.verbose('{0:>5}{1}: {2}'.format('', key.capitalize(), value))
                    # Test mode.  Skip remainder.
                    continue

                for retry in range(NUMBER_OF_RETRIES):
                    try:
                        response = self.pushover_request(data)
                    except RequestException as e:
                        log.warning('Could not get response from Pushover: %s. Try %s out of %s', e, retry + 1,
                                    NUMBER_OF_RETRIES)
                        continue
                    request_status = response.status_code
                    reset_time = datetime.datetime.fromtimestamp(
                        int(response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                    # error codes and messages from Pushover API
                    if request_status == 200:
                        remaining = response.headers['X-Limit-App-Remaining']
                        log.verbose(
                            'Pushover notification sent. Notification remaining until next resets: %s. '
                            'Next reset at: %s',
                            remaining, reset_time)
                        break
                    elif request_status == 500:
                        log.debug('Pushover notification failed, Pushover API having issues. Try %s out of %s',
                                  retry + 1, NUMBER_OF_RETRIES)
                        continue
                    elif request_status == 429:
                        log.error('Monthly pushover message limit reached. Next reset: %s', reset_time)
                        break
                    elif request_status >= 400:
                        errors = json.loads(response.content)['errors']
                        log.error('Pushover API error: %s', errors[0])
                        break
                    else:
                        log.error('Unknown error when sending Pushover notification')
                        break
                else:
                    log.error(
                        'Could not get response from Pushover after %s retries', NUMBER_OF_RETRIES)


class OutputPushover(object):
    """
    Example::

      pushover:
        userkey: <USER_KEY> (can also be a list of userkeys)
        apikey: <API_KEY>
        [device: <DEVICE_STRING>] (default: (none))
        [title: <MESSAGE_TITLE>] (default: "Download started" -- accepts Jinja2)
        [message: <MESSAGE_BODY>] (default uses series/tvdb name and imdb if available -- accepts Jinja2)
        [priority: <PRIORITY>] (default = 0 -- normal = 0, high = 1, silent = -1, emergency = 2)
        [url: <URL>] (default: "{{imdb_url}}" -- accepts Jinja2)
        [urltitle: <URL_TITLE>] (default: (none) -- accepts Jinja2)
        [sound: <SOUND>] (default: pushover default)
        [retry]: <RETRY>]

    Configuration parameters are also supported from entries (eg. through set).
    """

    schema = {
        'type': 'object',
        'properties': {
            'userkey': one_or_more({'type': 'string'}),
            'apikey': {'type': 'string'},
            'device': {'type': 'string'},
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'priority': {'oneOf': [
                {'type': 'number', 'minimum': -2, 'maximum': 2},
                {'type': 'string'}]},
            'url': {'type': 'string'},
            'url_title': {'type': 'string'},
            'sound': {'type': 'string'},
            'retry': {'type': 'integer', 'minimum': 30},
            'expire': {'type': 'integer', 'maximum': 86400},
            'callback': {'type': 'string', 'format': 'url'},
            'html': {'type': 'boolean'}
        },
        'required': ['userkey', 'apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        return Pushover(task, 'entries', 'accepted', task.options.test, config).notify()

    def notify(self, task, scope, iterate_on, test, config):
        return Pushover(task, scope, iterate_on, test, config).notify()


@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushover, 'pushover', api_ver=2, groups=['notifiers'])
