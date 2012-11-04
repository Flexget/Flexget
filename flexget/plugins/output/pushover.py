import logging
from flexget.plugin import register_plugin
from flexget.utils.template import RenderError

log = logging.getLogger("pushover")

__version__ = 0.1
headers = {"User-Agent": "FlexGet Pushover plugin/%s" % str(__version__)}
url = "https://api.pushover.net/1/messages.json"

class OutputPushover(object):
    """
    Example::

      pushover:
        userkey: <USER_KEY>
        apikey: <API_KEY>
        device: <DEVICE_STRING>

    Configuration parameters are also supported from entries (eg. through set).
    """

    def validator(self):
        from flexget import validator
        config = validator.factory("dict")
        config.accept("text", key="userkey", required=True)
        config.accept("text", key="apikey", required=True)
        config.accept("text", key="device", required=True)
        return config

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {"enabled": config}
        return config

    def on_task_output(self, task, config):
        # get the parameters
        config = self.prepare_config(config)
        for entry in task.accepted:

            if task.manager.options.test:
                log.info("Would send Pushover notification about: %s", entry["title"])
                continue

            userkey = entry.get("userkey", config["userkey"])
            apikey = entry.get("apikey", config["apikey"])
            device = entry.get("device", config["device"])

            # Send the request
            data = {"user": userkey, "token": apikey, "device": device,
                    "title": "New Flexget Download", "message": entry["title"]}
            response = task.requests.post(url, headers=headers, data=data, raise_status=False)

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
