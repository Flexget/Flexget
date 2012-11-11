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
        [device: <DEVICE_STRING>]
        [title: <MESSAGE_TITLE>]
        [priority: <PRIORITY>] (1 = high, -1 = silent)
        [url: <URL>]

    Configuration parameters are also supported from entries (eg. through set).
    """

    def validator(self):
        from flexget import validator
        config = validator.factory("dict")
        config.accept("text", key="userkey", required=True)
        config.accept("text", key="apikey", required=True)
        config.accept("text", key="device", required=False)
        config.accept("text", key="title", required=False)
        config.accept("integer", key="priority", required=False)
        config.accept("url", key="url", required=False)
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {"enabled": config}

        # Set the defaults
        config.setdefault("device", None)
        config.setdefault("title", "Download started")
        config.setdefault("priority", 0)
        config.setdefault("url", None)

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
            message = entry["title"]
            priority = config["priority"]
            url = entry.get("imdb_url", config["url"])

            # Attempt to render the entry's title field
            try:
                message = entry.render(message)
            except RenderError, e:
                log.warning("Problem rendering entry 'title' field: %s" % e)
                message = entry["title"]

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
            data = {"user": userkey, "token": apikey, "title": title, "message": message}
            if device:
                data["device"] = device
            if priority:
                data["priority"] = priority
            if url:
                data["url"] = url

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
