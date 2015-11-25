from __future__ import unicode_literals, division, absolute_import

import logging

from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError

log = logging.getLogger("pushover")

pushover_url = "https://api.pushover.net/1/messages.json"


class OutputPushover(object):
    """
    Example::

      pushover:
        userkey: <USER_KEY> (can also be a list of userkeys)
        apikey: <API_KEY>
        [device: <DEVICE_STRING>] (default: (none))
        [title: <MESSAGE_TITLE>] (default: "Download started" -- accepts Jinja2)
        [message: <MESSAGE_BODY>] (default: "{{series_name}} {{series_id}}" -- accepts Jinja2)
        [priority: <PRIORITY>] (default = 0 -- normal = 0, high = 1, silent = -1)
        [url: <URL>] (default: "{{imdb_url}}" -- accepts Jinja2)
        [urltitle: <URL_TITLE>] (default: (none) -- accepts Jinja2)
        [sound: <SOUND>] (default: pushover default)

    Configuration parameters are also supported from entries (eg. through set).
    """
    default_message = "{% if series_name is defined %}{{tvdb_series_name|d(series_name)}} " \
                      "{{series_id}} {{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} " \
                      "{{imdb_year}}{% else %}{{title}}{% endif %}"

    default_url = '{% if imdb_url is defined %}{{imdb_url}}{% endif %}'
    default_title = '{{task}}'

    schema = {
        'type': 'object',
        'properties': {
            'userkey': one_or_more({'type': 'string'}),
            'apikey': {'type': 'string'},
            'device': {'type': 'string'},
            'title': {'type': 'string'},
            'message': {'type': 'string'},
            'priority': {'oneOf': [
                {'type': 'number', 'minimum': -2, 'maximum': 1},
                {'type': 'string'}]},
            'url': {'type': 'string'},
            'urltitle': {'type': 'string'},
            'sound': {'type': 'string'}
        },
        'required': ['userkey', 'apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        if not isinstance(config['userkey'], list):
            config['userkey'] = [config['userkey']]

        apikey = config["apikey"]
        userkeys = config['userkey']

        # Loop through the provided entries
        for entry in task.accepted:

            # A Dict that hold parameters and their optional defaults. Used to set default if rendering fails
            parameters = {'title':
                              {'value': config.get("title"),
                               'default': self.default_title},
                          'message':
                              {'value': config.get("message"),
                               'default': self.default_message},
                          'url':
                              {'value': config.get("url"),
                               'default': self.default_url},
                          'urltitle':
                              {'value': config.get("urltitle")},
                          'priority':
                              {'value': config.get("priority")},
                          'sound':
                              {'value': config.get("sound")},
                          'device':
                              {'value': config.get("device")}
                          }

            for key, value in parameters.items():
                # Tried to render data in field
                try:
                    parameters[key]['value'] = entry.render(value.get('value'))
                except RenderError as e:
                    log.warning('Problem rendering %s: %s ' % (key, e))
                except ValueError:
                    pass

                # If field is empty or rendering fails, try to render field default if exists
                try:
                    parameters[key]['value'] = entry.render(value.get('default'))
                except ValueError:
                    pass

            for userkey in userkeys:
                # Build the request
                data = {"user": userkey,
                        "token": apikey
                        }
                # Get only filled values to send request
                for key, value in parameters.items():
                    if value.get('value'):
                        data[key] = value['value']

                # Check for test mode
                if task.options.test:
                    log.info("Test mode.  Pushover notification would be:")
                    for key, value in data.items():
                        log.verbose('{0:>5}{1}: {2}'.format('', key.capitalize(), value))
                    # Test mode.  Skip remainder.
                    continue

                # Make the request
                try:
                    response = task.requests.post(pushover_url, data=data, raise_status=False)
                except RequestException as e:
                    log.warning('Could not get response from Pushover: {}'.format(e))
                    return

                # Check if it succeeded
                request_status = response.status_code

                # error codes and messages from Pushover API
                if request_status == 200:
                    log.debug("Pushover notification sent")
                elif request_status == 500:
                    log.debug("Pushover notification failed, Pushover API having issues")
                    # TODO: Implement retrying. API requests 5 seconds between retries.
                elif request_status >= 400:
                    errors = json.loads(response.content)['errors']
                    log.error("Pushover API error: %s" % errors[0])
                else:
                    log.error("Unknown error when sending Pushover notification")


@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushover, "pushover", api_ver=2)
