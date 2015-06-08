from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError
from flexget.config_schema import one_or_more

log = logging.getLogger("pushalot")

pushalot_url = "https://pushalot.com/api/sendmessage"


class OutputPushalot(object):
    """
    Example::

      pushalot:
        token: <string> Authorization token (can also be a list of tokens) - Required
        title: <string> (default: task name -- accepts Jinja2)
        body: <string> (default: "{{series_name}} {{series_id}}" -- accepts Jinja2)
        link: <string> (default: "{{imdb_url}}" -- accepts Jinja2)
        linktitle: <string> (default: (none) -- accepts Jinja2)
        important: <boolean> (default is False)
        silent: <boolean< (default is False)
        image: <string> (default: (none) -- accepts Jinja2)
        source: <string> (default is "FlexGet")
        timetolive: <integer> (no default sent, default is set by Pushalot)

    Configuration parameters are also supported from entries (eg. through set).
    """
    default_body = "{% if series_name is defined %}{{tvdb_series_name|d(series_name)}} " \
                   "{{series_id}} {{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}{{imdb_name}} "\
                   "{{imdb_year}}{% else %}{{title}}{% endif %}"
    schema = {
        'type': 'object',
        'properties': {
            'token': one_or_more({'type': 'string'}),
            'title': {'type': 'string', 'default': "Task {{task}}"},
            'body': {'type': 'string', 'default': default_body},
            'link': {'type': 'string', 'default': '{% if imdb_url is defined %}{{imdb_url}}{% endif %}'},
            'linktitle': {'type': 'string', 'default': ''},
            'important': {'type': 'boolean', 'default': False},
            'silent': {'type': 'boolean', 'default': False},
            'image': {'type': 'string', 'default': ''},
            'source': {'type': 'string', 'default': 'FlexGet'},
            'timetolive': {'type': 'integer', 'default': 0},
        },
        'required': ['token'],
        'additionalProperties': False
    }

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        # Support for multiple tokens
        tokens = config["token"]
        if not isinstance(tokens, list):
            tokens = [tokens]

        # Loop through the provided entries
        for entry in task.accepted:

            title = config["title"]
            body = config["body"]
            link = config["link"]
            linktitle = config["linktitle"]
            important = config["important"]
            silent = config["silent"]
            image = config["image"]
            source = config["source"]
            timetolive = config["timetolive"]           

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

            # Attempt to render the link field
            try:
                link = entry.render(link)
            except RenderError as e:
                log.warning("Problem rendering 'link': %s" % e)
                link = entry.get("imdb_url", "")

            # Attempt to render the linktitle field
            try:
                linktitle = entry.render(linktitle)
            except RenderError as e:
                log.warning("Problem rendering 'linktitle': %s" % e)
                linktitle = ""

            try:
                image = entry.render(image)
            except RenderError as e:
                log.warning("Problem rendering 'image': %s" % e)
                image = ""

            for token in tokens:
                # Build the request
                data = {"AuthorizationToken": token, "title": title, "body": body,
                        "link": link, "linktitle": linktitle, "important": important,
                        "silent": silent, "image": image, "source": source,
                        "timetolive": timetolive}
                # Check for test mode
                if task.options.test:
                    log.info("Test mode.  Pushalot notification would be:")
                    log.info("    Title: %s" % title)
                    log.info("    body: %s" % body)
                    log.info("    link: %s" % link)
                    log.info("    link Title: %s" % linktitle)
                    log.info("    token: %s" % token)
                    log.info("    important: %s" % important)
                    log.info("    silent: %s" % silent)
                    log.info("    image: %s" % image)
                    log.info("    source: %s" % source)
                    log.info("    timetolive: %s" % timetolive)
                    # Test mode.  Skip remainder.
                    continue

                # Make the request
                response = task.requests.post(pushalot_url, data=data, raise_status=False)

                # Check if it succeeded
                request_status = response.status_code

                # error codes and bodys from Pushalot API
                if request_status == 200:
                    log.debug("Pushalot notification sent")
                elif request_status == 500:
                    log.debug("Pushalot notification failed, Pushalot API having issues")
                    # TODO: Implement retrying. API requests 5 seconds between retries.
                elif request_status >= 400:
                    errors = json.loads(response.content)
                    log.error("Pushalot API error: %s" % errors['Description'])
                else:
                    log.error("Unknown error when sending Pushalot notification")


@event('plugin.register')
def register_plugin():
    plugin.register(OutputPushalot, "pushalot", api_ver=2)
