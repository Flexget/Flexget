import socket

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = "cronitor"

logger = logger.bind(name=plugin_name)


class Cronitor:
    """
    Example::
      cronitor: ABC123

    Or:
      cronitor:
        monitor_code: ABC123
        on_start: yes
        on_abort: no
        message: Ping
        host: foo.bar
        auth_key: secret
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

    @staticmethod
    def prepare_config(config):
        if isinstance(config, str):
            config = {"monitor_code": config}
        config.setdefault("on_start", True)
        config.setdefault("on_abort", True)
        config.setdefault("host", socket.gethostname())
        return config

    def _send_request(self, status, config, task_name):
        url = self.base_url.format(monitor_code=config["monitor_code"], status=status)
        message = config.get(
            "message", "{task} task {status}".format(task=task_name, status=status)
        )
        data = {"msg": message, "host": config["host"]}
        if config.get("auth_key"):
            data["auth_key"] = config["auth_key"]
        try:
            rsp = requests.get(url, params=data)
            rsp.raise_for_status()
        except RequestException as e:
            raise PluginWarning("Could not report to cronitor: {}".format(e))

    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        if not config["on_start"]:
            return
        self._send_request("run", config, task.name)

    def on_task_abort(self, task, config):
        config = self.prepare_config(config)
        if not config["on_abort"]:
            return
        self._send_request("fail", config, task.name)

    def on_task_exit(self, task, config):
        config = self.prepare_config(config)
        self._send_request("complete", config, task.name)


@event("plugin.register")
def register_plugin():
    plugin.register(Cronitor, plugin_name, api_ver=2)
