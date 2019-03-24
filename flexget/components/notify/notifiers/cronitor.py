from builtins import *

import logging
import socket
from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from requests.exceptions import RequestException
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = "cronitor"

log = logging.getLogger(plugin_name)


class Cronitor(object):
    """
    Example::
      cronitor:
        monitor_code: ABC123
    """

    base_url = "https://cronitor.link/{monitor_code}/{status}"

    schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "monitor_code": {"type": "string"},
                    "on_start": {"type": "boolean"},
                    "on_abort": {"type": "boolean"},
                    "message": {"type": "string"},
                    "host": {"type": "string"},
                    "auth_key": {"type": "string"},
                },
                "required": ["monitor_code"],
                "additionalProperties": False,
            },
            {"type": "string"},
        ]
    }

    def __init__(self):
        self.config = None
        self.task_name = None

    @staticmethod
    def prepare_config(config):
        if isinstance(config, str):
            config = {"monitor_code": config}
        config.setdefault("on_start", True)
        config.setdefault("on_start", True)
        config.setdefault("host", socket.gethostname())
        return config

    def _send_request(self, status):
        url = self.base_url.format(monitor_code=self.config["monitor_code"], status=status)
        message = self.config.get(
            "message", "{task} task {status}".format(task=self.task_name, status=status)
        )
        data = {"msg": message, "host": self.config["host"]}
        if self.config.get("auth_key"):
            data["auth_key"] = self.config["auth_key"]
        try:
            rsp = requests.get(url, params=data)
            rsp.raise_for_status()
        except RequestException as e:
            raise PluginWarning("Could not report to cronitor: {}".format(e))

    def on_task_start(self, task, config):
        self.config = self.prepare_config(config)
        self.task_name = task.name
        if not self.config["on_start"]:
            return
        self._send_request("run")

    def on_task_abort(self, task, config):
        if not self.config["on_abort"]:
            return
        self._send_request("fail")

    def on_task_exit(self, task, config):
        self._send_request("complete")


@event("plugin.register")
def register_plugin():
    plugin.register(Cronitor, plugin_name, api_ver=2)
