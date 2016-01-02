from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from flexget.config_schema import one_or_more

log = logging.getLogger('hipchat')


class OutputHipchat(object):
    """
    Example::
      hipchat:
        auth_token: <AUTH_TOKEN>
        room_key: <ROOM_KEY>
        [color: green|yellow|red|grey|purple (default: green)]
        [notify: true|false (default: false)]
        [title: <TITLE> (default: "New download started:")]
        [message: <MESSAGE_BODY> (default: "{{ series_name }} {{ series_id }} {{ quality }}" -- accepts Jinja2)]
        [url: <HIPCHAT_URL> (default: https://api.hipchat.com)]
    Configuration parameters are also supported from entries (eg. through set).
    """
    default_message = ('{% if series_name is defined %}{{tvdb_series_name|d(series_name)}} {{series_id}} '
                        '{{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} '
                        '{{imdb_year}}{% else %}{{title}}{% endif %}')
    schema = {
        'type': 'object',
        'properties': {
            'auth_token': one_or_more({'type': 'string'}),
            'room_key': one_or_more({'type': 'string'}),
            'color': {'type': 'string', 'default': 'green'},
            'notify': {'type': 'string', 'default': 'false'},
            'title': {'type': 'string', 'default': 'New download started:'},
            'message': {'type': 'string', 'default': default_message},
            'url': {'type': 'string', 'default': 'https://api.hipchat.com'},
        },
        'required': ['auth_token', 'room_key'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        for entry in task.accepted:
            auth_token = config['auth_token']
            room_key = config['room_key']
            color = config['color']
            notify = config['notify']
            title = config['title']
            message = config['message']
            url = config['url']

            # Attempt to render the color field
            try:
                color = entry.render(color)
            except RenderError as e:
                log.warning('Problem rendering `color`: %s' % e)
                color = 'green'

            # Attempt to render the notify field
            try:
                notify = entry.render(notify)
            except RenderError as e:
                log.warning('Problem rendering `notify`: %s' % e)
                notify = 'false'

            # Attempt to render the title field
            try:
                title = entry.render(title)
            except RenderError as e:
                log.warning('Problem rendering `title`: %s' % e)
                title = 'New download started:'

            # Attempt to render the message field
            try:
                message = entry.render(message)
            except RenderError as e:
                log.warning('Problem rendering `message`: %s' % e)
                message = entry['title']

            # Attempt to render the url field
            try:
                url = entry.render(url)
            except RenderError as e:
                log.warning('Problem rendering `url`: %s' % e)
                url = 'https://api.hipchat.com'

            full_url = '%s/v2/room/%s/notification?auth_token=%s' % (url, room_key, auth_token)

            self.send_push(task, auth_token, room_key, color, notify, title, message, full_url)

    def send_push(self, task, auth_token, room_key, color, notify, title, message, url):

        body = '%s %s' % (title, message)

        data = {'color': color, 'message': body, 'notify': notify, 'message_format': "text"}

        # Check for test mode
        if task.options.test:
            log.info('Test mode. Hipchat notification would be:')
            log.info('      Auth Token: %s' % auth_token)
            log.info('      Room Key: %s' % room_key)
            log.info('      Color: %s' % color)
            log.info('      Notify: %s' % notify)
            log.info('      Title: %s' % title)
            log.info('      Message: %s' % message)
            log.info('      URL: %s' % url)
            log.info('      Raw Data: %s' % json.dumps(data))
            # Test mode.  Skip remainder.
            return

        # Make the request
        headers = {
            'Content-Type': 'application/json'
        }
        response = task.requests.post(url, headers=headers, data=json.dumps(data), raise_status=False)

        # Check if it succeeded
        request_status = response.status_code

        # error codes and messages from Hipchat API
        if request_status == 200:
            log.debug('Hipchat notification sent')
        elif request_status == 500:
            log.warning('Hipchat notification failed, Hipchat API having issues')
            # TODO: Implement retrying. API requests 5 seconds between retries.
        elif request_status >= 400:
            if response.content:
                try:
                    error = json.loads(response.content)['error']
                except ValueError:
                    error = 'Unknown Error (Invalid JSON returned)'
            log.error('Hipchat API error: %s' % error['message'])
        else:
            log.error('Unknown error when sending Hipchat notification')


@event('plugin.register')
def register_plugin():
    plugin.register(OutputHipchat, 'hipchat', api_ver=2)
