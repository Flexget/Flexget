from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.template import RenderError

log = logging.getLogger('notify')


class Notify(object):
    def send_notification(self, title, message, notifiers, template_renderer=None):
        """
        Send a notification out to the given `notifiers` with a given `title` and `message`.
        If `template_renderer` is specified, `title`, `message`, as well as any string options in a notifier's config
        will be rendered using this function before sending the message.

        :param str title: Title of the notification.
        :param str message: Body of the notification.
        :param list notifiers: A list of configured notifier output plugins.
        :param template_renderer: A function that should be used to render any jinja strings in the configuration.
        """
        if template_renderer:
            try:
                title = template_renderer(title)
            except RenderError as e:
                log.error('Error rendering notification title: %s', e)
            try:
                message = template_renderer(message)
            except RenderError as e:
                log.error('Error rendering notification body: %s', e)
        for notifier in notifiers:
            for notifier_name, notifier_config in notifier.items():
                notifier = plugin.get_plugin_by_name(notifier_name).instance

                rendered_config = {}

                # If a template renderer is specified, try to render all the notifier config values
                if template_renderer:
                    for attribute, value in notifier_config.items():
                        if isinstance(value, str):
                            try:
                                rendered_config[attribute] = template_renderer(value)
                            except RenderError as e:
                                log.error('Error rendering %s config field %s: %s', notifier_name, attribute, e)
                                rendered_config[attribute] = notifier_config[attribute]
                        else:
                            rendered_config[attribute] = notifier_config[attribute]
                else:
                    rendered_config = notifier_config

                log.debug('Sending a notification to `%s`', notifier_name)
                try:
                    notifier.notify(title, message, rendered_config)  # TODO: Update notifiers for new api
                except PluginWarning as e:
                    log.warning('Error while sending notification to `%s`: %s', notifier_name, e.value)
                else:
                    log.verbose('Successfully sent a notification to `%s`', notifier_name)


@event('plugin.register')
def register_plugin():
    plugin.register(Notify, 'notify', api_ver=2)

    plugin.register_task_phase('notify', before='exit')  # TODO: something so this phase doesn't cause aborts
