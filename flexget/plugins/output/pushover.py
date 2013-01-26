from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin
from flexget.utils.template import RenderError

log = logging.getLogger("pushover")

__version__ = 0.1
client_headers = {"User-Agent": "FlexGet Pushover plugin/%s" % str(__version__)}
pushover_url = "https://api.pushover.net/1/messages.json"

class OutputPushover(object):
    """
    Example::

      pushover:
        userkey: <USER_KEY>
        apikey: <API_KEY>
        [device: <DEVICE_STRING>] (default: (none))
        [title: <MESSAGE_TITLE>] (default: "Download started" -- accepts Jinja)
        [message: <MESSAGE_BODY>] (default: "{{series_name}} {{series_id}}" -- accepts Jinja)
        [priority: <PRIORITY>] (default = 0 -- normal = 0, high = 1, silent = -1)
        [url: <URL>] (default: "{{imdb_url}}" -- accepts Jinja)

    Configuration parameters are also supported from entries (eg. through set).
    """

    def validator(self):
        from flexget import validator
        config = validator.factory("dict")
        config.accept("text", key="userkey", required=True)
        config.accept("text", key="apikey", required=True)
        config.accept("text", key="device", required=False)
        config.accept("text", key="title", required=False)
        config.accept("text", key="message", required=False)
        config.accept("integer", key="priority", required=False)
        config.accept("url", key="url", required=False)
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {"enabled": config}

        # Set the defaults
        config.setdefault("device", None)
        config.setdefault("title", "Download from {{task}}")
        config.setdefault("message", """{% if series_name is defined %}{{series_name_tvdb|d(series_name)}} {{series_id}} {{ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} {{imdb_year}}{% else %}{{title}}{% endif %}""")
        config.setdefault("priority", 0)
        config.setdefault("url", "{% if imdb_url is defined %}{{imdb_url}}{% endif %}")

        return config

    def on_task_output(self, task, config):
        # get the parameters
        config = self.prepare_config(config)

        # Loop through the provided entries
        for entry in task.accepted:
            # Set a bunch of local variables from the config and the entry
            userkey = config["userkey"]
            apikey = config["apikey"]
            device = config["device"]
            title = config["title"]
            message = config["message"]
            priority = config["priority"]
            url = config["url"]

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

            # Check for test mode
            if task.manager.options.test:
                log.info("Test mode.  Pushover notification would be:")
                if device:
                    log.info("    Device: %s" % device)
                else:
                    log.info("    Device: [broadcast]")
                log.info("    Title: %s" % title)
                log.info("    Message: %s" % message)
                log.info("    URL: %s" % url)
                log.info("    Priority: %d" % priority)

                # Test mode.  Skip remainder.
                continue

            # Build the request
            data = {"user": userkey, "token": apikey, "title": title, "message": message, "url": url}
            if device:
                data["device"] = device
            if priority:
                data["priority"] = priority

            # Make the request
            response = task.requests.post(pushover_url, headers=client_headers, data=data, raise_status=False)

            # Check if it succeeded
            request_status = response.status_code

            # error codes and messages from Pushover API
            if request_status == 200:
                log.debug("Pushover notification sent")
            elif request_status >= 400:
                log.error("Bad input, the parameters you provided did not validate")
            else:
                log.error("Unknown error when sending Pushover notification")

register_plugin(OutputPushover, "pushover", api_ver=2)
