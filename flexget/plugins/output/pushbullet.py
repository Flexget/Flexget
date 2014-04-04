from __future__ import unicode_literals, division, absolute_import
import logging
import base64

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError

log = logging.getLogger("pushbullet")

__version__ = 0.1
client_headers = {"User-Agent": "FlexGet Pushbullet plugin/%s" % str(__version__)}
pushbullet_url = "https://api.pushbullet.com/api/pushes"


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

    def validator(self):
        from flexget import validator
        config = validator.factory("dict")
        config.accept("text", key="apikey", required=True)
        config.accept("text", key="device", required=False)
        config.accept("list", key="device").accept("text")
        config.accept("text", key="title", required=False)
        config.accept("text", key="body", required=False)
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {"enabled": config}

        # TODO: don't assume it's a download
        config.setdefault("title", "{{task}} - Download started")
        # TODO: use template file
        config.setdefault("body", "{% if series_name is defined %}{{tvdb_series_name|d(series_name)}} "
                                     "{{series_id}} {{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} "
                                     "{{imdb_year}}{% else %}{{title}}{% endif %}")
        config.setdefault("device", None)
        return config

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # get the parameters
        config = self.prepare_config(config)

        # Support for multiple devices 
        devices = config["device"]
        if not isinstance(devices, list):
            devices = [devices]
 
        # Set a bunch of local variables from the config
        apikey = config["apikey"]
        device = config["device"]
            
        client_headers["Authorization"] = "Basic %s" % base64.b64encode(apikey)
        
        if task.options.test:
            log.info("Test mode. Pushbullet configuration:")
            log.info("    API_KEY: %s" % apikey)
            log.info("    Type: Note")
            log.info("    Device: %s" % device)

        # Loop through the provided entries
        for entry in task.accepted:

            title = config["title"]
            body = config["body"]

            # Attempt to render the title field
            try:
                title = entry.render(title)
            except RenderError as e:
                log.warning("Problem rendering 'title': %s" % e)
                title = "Download started"

            # Attempt to render the body field
            try:
                body = entry.render(body)
            except RenderError as e:
                log.warning("Problem rendering 'body': %s" % e)
                body = entry["title"]

            for device in devices:
                # Build the request
                if not device:
                    data = {"type": "note", "title": title, "body": body}
                else:
                    data = {"device_iden": device, "type": "note", "title": title, "body": body}

                # Check for test mode
                if task.options.test:
                    log.info("Test mode. Pushbullet notification would be:")
                    log.info("    Title: %s" % title)
                    log.info("    Body: %s" % body)
                    
                    # Test mode.  Skip remainder.
                    continue

                # Make the request
                response = task.requests.post(pushbullet_url, headers=client_headers, data=data, raise_status=False)

                # Check if it succeeded
                request_status = response.status_code

                # error codes and messages from Pushbullet API
                if request_status == 200:
                    log.debug("Pushbullet notification sent")
                elif request_status == 500:
                    log.warning("Pushbullet notification failed, Pushbullet API having issues")
                    #TODO: Implement retrying. API requests 5 seconds between retries.
                elif request_status >= 400:
                    error = json.loads(response.content)['error']
                    log.error("Pushbullet API error: %s" % error['message'])
                else:
                    log.error("Unknown error when sending Pushbullet notification")

@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushbullet, "pushbullet", api_ver=2)