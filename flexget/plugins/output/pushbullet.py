from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import base64

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from flexget.config_schema import one_or_more

log = logging.getLogger('pushbullet')

pushbullet_url = 'https://api.pushbullet.com/v2/pushes'


class OutputPushbullet(object):
    """
    Example::

      pushbullet:
        apikey: <API_KEY>
        [device: <DEVICE_IDEN> (can also be a list of device idens, or don't specify any idens to send to all devices)]
        [email: <EMAIL_ADDRESS> (can also be a list of user email addresses)]
        [channel: <CHANNEL_TAG> (you can only specify device / email or channel tag. cannot use both.)]
        [title: <MESSAGE_TITLE>] (default: "{{task}} - Download started" -- accepts Jinja2)
        [body: <MESSAGE_BODY>] (default: "{{series_name}} {{series_id}}" -- accepts Jinja2)

    Configuration parameters are also supported from entries (eg. through set).
    """
    default_body = ('{% if series_name is defined %}{{tvdb_series_name|d(series_name)}} {{series_id}} '
                    '{{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} '
                    '{{imdb_year}}{% else %}{{title}}{% endif %}')
    schema = {
        'type': 'object',
        'properties': {
            'apikey': one_or_more({'type': 'string'}),
            'device': one_or_more({'type': 'string'}),
            'email': one_or_more({'type': 'string'}),
            'title': {'type': 'string', 'default': '{{task}} - Download started'},
            'body': {'type': 'string', 'default': default_body},
            'url': {'type': 'string'},
            'channel': {'type': 'string'},
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        devices = config.get('device', [])
        if not isinstance(devices, list):
            devices = [devices]

        emails = config.get('email', [])
        if not isinstance(emails, list):
            emails = [emails]

        apikeys = config.get('apikey', [])
        if not isinstance(apikeys, list):
            apikeys = [apikeys]

        for entry in task.accepted:
            title = config['title']
            body = config['body']
            url = config.get('url')
            channel = config.get('channel')

            # Attempt to render the title field
            try:
                title = entry.render(title)
            except RenderError as e:
                log.warning('Problem rendering `title`: %s' % e)
                title = 'Download started'

            # Attempt to render the body field
            try:
                body = entry.render(body)
            except RenderError as e:
                log.warning('Problem rendering `body`: %s' % e)
                body = entry['title']

            # Attempt to render the url field
            if url:
                try:
                    url = entry.render(url)
                except RenderError as e:
                    log.warning('Problem rendering `url`: %s' % e)

            for apikey in apikeys:
                if channel:
                    self.send_push(task, apikey, title, body, url, channel, 'channel_tag')
                elif devices or emails:
                    for device in devices:
                        self.send_push(task, apikey, title, body, url, device, 'device_iden')
                    for email in emails:
                        self.send_push(task, apikey, title, body, url, email, 'email')
                else:
                    self.send_push(task, apikey, title, body, url)

    def send_push(self, task, api_key, title, body, url=None, destination=None, destination_type=None):

        if url:
            push_type = 'link'
        else:
            push_type = 'note'

        data = {'type': push_type, 'title': title, 'body': body}
        if url:
            data['url'] = url
        if destination:
            data[destination_type] = destination

        # Check for test mode
        if task.options.test:
            log.info('Test mode. Pushbullet notification would be:')
            log.info('    API Key: %s' % api_key)
            log.info('    Type: %s' % push_type)
            log.info('    Title: %s' % title)
            log.info('    Body: %s' % body)
            if destination:
                log.info('    Destination: %s (%s)' % (destination, destination_type))
            if url:
                log.info('    URL: %s' % url)
            log.info('    Raw Data: %s' % json.dumps(data))
            # Test mode.  Skip remainder.
            return

        # Make the request
        headers = {
            'Authorization': b'Basic ' + base64.b64encode(api_key.encode('ascii')),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Flexget'
        }
        response = task.requests.post(pushbullet_url, headers=headers, data=json.dumps(data), raise_status=False)

        # Check if it succeeded
        request_status = response.status_code

        # error codes and messages from Pushbullet API
        if request_status == 200:
            log.debug('Pushbullet notification sent')
        elif request_status == 500:
            log.warning('Pushbullet notification failed, Pushbullet API having issues')
            # TODO: Implement retrying. API requests 5 seconds between retries.
        elif request_status >= 400:
            error = 'Unknown error'
            if response.content:
                try:
                    error = response.json()['error']['message']
                except ValueError as e:
                    error = 'Unknown Error (Invalid JSON returned): %s' % e
            log.error('Pushbullet API error: %s' % error)
        else:
            log.error('Unknown error when sending Pushbullet notification')


@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushbullet, 'pushbullet', api_ver=2)
