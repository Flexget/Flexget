from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import datetime
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.notifier import Notifier
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from flexget.utils.template import RenderError
from requests.exceptions import RequestException

log = logging.getLogger('pushover')

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
NUMBER_OF_RETRIES = 3

requests = RequestSession(max_retries=5)
requests.add_domain_limiter(TimedLimiter('api.pushover.net.cc', '5 seconds'))


class Pushover(Notifier):
    def __init__(self, task, scope, iterate_on, test, config):
        super(Pushover, self).__init__(task, scope, iterate_on, test, config)
        self.config = self.prepare_config(config)

    defaults = {
        'message': '{% if series_name is defined %}'
                   '{{ tvdb_series_name|d(series_name) }} '
                   '{{series_id}} {{tvdb_ep_name|d('')}}'
                   '{% elif imdb_name is defined %}'
                   '{{imdb_name}} {{imdb_year}}'
                   '{% elif title is defined %}'
                   '{{ title }}'
                   '{% else %}'
                   'Task has {{ task.accepted|length }} accepted entries'
                   '{% endif %}',
        'url': '{% if imdb_url is defined %}{{imdb_url}}{% endif %}',
        'title': '{{ task_name }}'
    }

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
        # Loop through the provided cotainers and entities
        for container in self.iterate_on:
            for entity in container:
                for key, value in list(self.config.items()):
                    if key in ['apikey', 'userkey']:
                        continue

                    # Special case for html key
                    if key == 'html' and value is True:
                        data['html'] = 1
                        continue

                    # Tried to render data in field
                    try:
                        data[key] = entity.render(value)
                    except RenderError as e:
                        log.warning('Problem rendering {0}: {1}'.format(key, e))
                        data[key] = None
                    except ValueError:
                        data[key] = None

                    # If field is empty or rendering fails, try to render field default if exists
                    if not data[key]:
                        try:
                            data[key] = entity.render(self.defaults.get(key))
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
                        log.info('Test mode. Pushover notification would be:')
                        for key, value in list(data.items()):
                            log.verbose('%10s: %s', key.capitalize(), value)
                        # Test mode.  Skip remainder.
                        continue

                    try:
                        response = requests.post(PUSHOVER_URL, data=data)
                    except RequestException as e:
                        if e.response.status_code == 429:
                            reset_time = datetime.datetime.fromtimestamp(
                                int(e.response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                            message = 'Monthly pushover message limit reached. Next reset: %s', reset_time
                        else:
                            message = 'Could not send notification to Pushover: %s', e.response.json()['errors']
                        log.error(*message)
                        return

                    reset_time = datetime.datetime.fromtimestamp(
                        int(response.headers['X-Limit-App-Reset'])).strftime('%Y-%m-%d %H:%M:%S')
                    remaining = response.headers['X-Limit-App-Remaining']
                    log.verbose('Pushover notification sent. Notifications remaining until next reset: %s. '
                                'Next reset at: %s', remaining, reset_time)


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
        # Send default values for backwards comparability
        return Pushover(task, 'entries', 'accepted', task.options.test, config).notify()

    def notify(self, task, scope, iterate_on, test, config):
        return Pushover(task, scope, iterate_on, test, config).notify()


@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushover, 'pushover', api_ver=2, groups=['notifiers'])
