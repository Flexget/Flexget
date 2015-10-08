from __future__ import unicode_literals, division, absolute_import
import logging
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from flexget.config_schema import one_or_more

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
                      "{{series_id}} {{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} "\
                      "{{imdb_year}}{% else %}{{title}}{% endif %}"
    schema = {
        'type': 'object',
        'properties': {
            'userkey': one_or_more({'type': 'string'}),
            'apikey': {'type': 'string'},
            'device': {'type': 'string', 'default': ''},
            'title': {'type': 'string', 'default': "{{task}}"},
            'message': {'type': 'string', 'default': default_message},
            'priority': {'type': 'integer', 'default': 0},
            'url': {'type': 'string', 'default': '{% if imdb_url is defined %}{{imdb_url}}{% endif %}'},
            'urltitle': {'type': 'string', 'default': ''},
            'sound': {'type': 'string', 'default': ''}
        },
        'required': ['userkey', 'apikey'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        # Support for multiple userkeys
        userkeys = config["userkey"]
        if not isinstance(userkeys, list):
            userkeys = [userkeys]

        # Set a bunch of local variables from the config
        apikey = config["apikey"]
        device = config["device"]
        priority = config["priority"]
        sound = config["sound"]

        # Loop through the provided entries
        for entry in task.accepted:

            title = config["title"]
            message = config["message"]
            url = config["url"]
            urltitle = config["urltitle"]

            # Attempt to render the title field
            try:
                title = entry.render(title)
            except RenderError as e:
                log.warning("Problem rendering 'title': %s" % e)
                title = "Download started"

            # Attempt to render the message field
            try:
                message = entry.render(message)
            except RenderError as e:
                log.warning("Problem rendering 'message': %s" % e)
                message = entry["title"]

            # Attempt to render the url field
            try:
                url = entry.render(url)
            except RenderError as e:
                log.warning("Problem rendering 'url': %s" % e)
                url = entry.get("imdb_url", "")

            # Attempt to render the urltitle field
            try:
                urltitle = entry.render(urltitle)
            except RenderError as e:
                log.warning("Problem rendering 'urltitle': %s" % e)
                urltitle = ""

            for userkey in userkeys:
                # Build the request
                data = {"user": userkey, "token": apikey, "title": title,
                        "message": message, "url": url, "url_title": urltitle}
                if device:
                    data["device"] = device
                if priority:
                    data["priority"] = priority
                if sound:
                    data["sound"] = sound

                # Check for test mode
                if task.options.test:
                    log.info("Test mode.  Pushover notification would be:")
                    if device:
                        log.info("    Device: %s" % device)
                    else:
                        log.info("    Device: [broadcast]")
                    log.info("    Title: %s" % title)
                    log.info("    Message: %s" % message)
                    log.info("    URL: %s" % url)
                    log.info("    URL Title: %s" % urltitle)
                    log.info("    Priority: %d" % priority)
                    log.info("    userkey: %s" % userkey)
                    log.info("    apikey: %s" % apikey)
                    log.info("    sound: %s" % sound)

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
