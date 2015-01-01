from __future__ import unicode_literals, division, absolute_import
import logging
import base64

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from flexget.config_schema import one_or_more

log = logging.getLogger('pushbullet')

pushbullet_url = 'https://api.pushbullet.com/api/pushes'


class OutputPushbullet(object):
    """
    Example::

      pushbullet:
        apikey: <API_KEY>
        device: <DEVICE_IDEN> (can also be a list of device idens, or don't specify any idens to send to all devices)
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
            'apikey': {'type': 'string'},
            'device': one_or_more({'type': 'string'}),
            'title': {'type': 'string', 'default': '{{task}} - Download started'},
            'body': {'type': 'string', 'default': default_body},
            'url': {'type': 'string'},
        },
        'required': ['apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        # Support for multiple devices
        devices = config.get('device')
        if not isinstance(devices, list):
            devices = [devices]

        # Support for urls
        push_type = 'link' if config.has_key('url') else 'note'

        # Set a bunch of local variables from the config
        apikey = config['apikey']

        client_headers = {'Authorization': 'Basic %s' % base64.b64encode(apikey)}

        if task.options.test:
            log.info('Test mode. Pushbullet configuration:')
            log.info('    API_KEY: %s' % apikey)
            log.info('    Type: %s' % push_type)
            log.info('    Device: %s' % devices)

        # Loop through the provided entries
        for entry in task.accepted:

            title = config['title']
            body = config['body']
            url = config.get('url', '')

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
            if push_type is 'link':
                try:
                    url = entry.render(url)
                except RenderError as e:
                    log.warning('Problem rendering `url`: %s' % e)

            for device in devices:
                # Build the request
                data = {'type': push_type, 'title': title, 'body': body}
                if push_type is 'link':
                    data['url'] = url
                if device:
                    data['device_iden'] = device

                # Check for test mode
                if task.options.test:
                    log.info('Test mode. Pushbullet notification would be:')
                    log.info('    Type: %s' % push_type)
                    log.info('    Title: %s' % title)
                    log.info('    Body: %s' % body)
                    if push_type is 'link':
                         log.info('    URL: %s' % url)
                    # Test mode.  Skip remainder.
                    continue

                # Make the request
                response = task.requests.post(pushbullet_url, headers=client_headers, data=data, raise_status=False)

                # Check if it succeeded
                request_status = response.status_code

                # error codes and messages from Pushbullet API
                if request_status == 200:
                    log.debug('Pushbullet notification sent')
                elif request_status == 500:
                    log.warning('Pushbullet notification failed, Pushbullet API having issues')
                    #TODO: Implement retrying. API requests 5 seconds between retries.
                elif request_status >= 400:
                    error = json.loads(response.content)['error']
                    log.error('Pushbullet API error: %s' % error['message'])
                else:
                    log.error('Unknown error when sending Pushbullet notification')

@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushbullet, 'pushbullet', api_ver=2)
