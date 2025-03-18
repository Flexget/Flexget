import socket

import requests
from loguru import logger

from flexget import plugin
from flexget.event import event

try:
    import mechanicalsoup
except ImportError:
    mechanicalsoup = None


logger = logger.bind(name="formlogin")


class FormLogin:
    """Login on form."""

    schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "format": "url"},
            "username": {"type": "string"},
            "password": {"type": "string"},
            "userfield": {"type": "string"},
            "passfield": {"type": "string"},
        },
        "required": ["url", "username", "password"],
        "additionalProperties": False,
    }

    def on_task_start(self, task, config):
        if not mechanicalsoup:
            raise plugin.PluginError(
                "mechanicalsoup required (python module), please install it.", logger
            )

        userfield = config.get("userfield", "username")
        passfield = config.get("passfield", "password")

        url = config["url"]
        username = config["username"]
        password = config["password"]

        # Mechanicalsoup will override our session user agent header unless we explicitly pass it in
        user_agent = task.requests.headers.get("User-Agent")
        br = mechanicalsoup.StatefulBrowser(session=task.requests, user_agent=user_agent)

        try:
            response = br.open(url)
        except requests.RequestException:
            # TODO: improve error handling
            logger.opt(exception=True).debug("Exception getting login page.")
            raise plugin.PluginError("Unable to get login page", logger)

        # br.set_debug(True)

        num_forms = len(br.get_current_page().find_all("form"))
        if not num_forms:
            raise plugin.PluginError(f"Unable to find any forms on {url}", logger)
        try:
            for form_num in range(num_forms):
                br.select_form(nr=form_num)
                try:
                    br[userfield] = username
                    br[passfield] = password
                    break
                except mechanicalsoup.LinkNotFoundError:
                    pass
            else:
                received = task.manager.config_base / "received"
                if not received.is_dir():
                    received.mkdir()
                filename = received / f"{task.name}.formlogin.html"
                with filename.open("wb") as f:
                    f.write(response.content)
                logger.critical(
                    "I have saved the login page content to {} for you to view", filename
                )
                raise plugin.PluginError("Unable to find login fields", logger)
        except socket.timeout:
            raise plugin.PluginError(f"Timed out on url {url}")

        try:
            br.submit_selected()
        except requests.RequestException:
            logger.opt(exception=True).debug("Exception submitting login form.")
            raise plugin.PluginError("Unable to post login form", logger)


@event("plugin.register")
def register_plugin():
    plugin.register(FormLogin, "form", api_ver=2)
