from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils import json
from flexget.utils.template import RenderError

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
    default_body = ("{% if series_name is defined %}{{tvdb_series_name|d(series_name)}}" +
                    "{{series_id}} {{tvdb_ep_name|d('')}}{% elif imdb_name is defined %}" +
                    "{{imdb_name}} {{imdb_year}}{% else %}{{title}}{% endif %}")
    schema = {'oneof': [
        {'type': 'object',
         'properties': {
             'token': one_or_more({'type': 'string'}),
             'title': {'type': 'string'},
             'body': {'type': 'string'},
             'link': {'type': 'string'},
             'linktitle': {'type': 'string'},
             'important': {'type': 'boolean'},
             'silent': {'type': 'boolean'},
             'image': {'type': 'string'},
             'source': {'type': 'string'},
             'timetolive': {'type': 'integer'},
         },
         'required': ['token'],
         'additionalProperties': False},
        {'type': 'string'}
    ]
    }

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'token': config}

        if isinstance(config.get('token'), basestring):
            config['token'] = [config['token']]

        config.setdefault('title', "Task {{task}}")
        config.setdefault('body', self.default_body)
        config.setdefault('link', '{% if imdb_url is defined %}{{imdb_url}}{% endif %}')
        config.setdefault('linktitle', '')
        config.setdefault('important', False)
        config.setdefault('silent', False)
        config.setdefault('image', '')
        config.setdefault('source', 'FlexGet')
        config.setdefault('timetolive', 0)

        return config

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):

        config = self.prepare_config(config)
        tokens = config.get('token')

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
