"""
This plugin adds a notification framework which can be used by other plugins to send messages to the user,
via a transport service configurable by the user.

Sending Messages
----------------
A plugin who wishes to send messages using this notification framework should import this plugin, then call the
`send_notification` method. Example::

    from flexget import plugin

    send_notification = plugin.get_plugin_by_name('notification_framework').instance.send_notification
    send_notification('the title', 'the message', the_notifiers)

Delivering Messages
-------------------
To implement a plugin that can deliver messages, it should implement a `notify` method, which takes
`(title, message, config)` as arguments. The plugin should also have a `schema` attribute which is a JSON schema that
describes the config format for the plugin.

"""


from jinja2 import Template
from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.template import RenderError

logger = logger.bind(name='notify')

NOTIFY_VIA_SCHEMA = {
    'type': 'array',
    'items': {
        'allOf': [
            {'$ref': '/schema/plugins?interface=notifiers'},
            {
                'minProperties': 1,
                'maxProperties': 1,
                'error_maxProperties': 'Plugin options indented 2 more spaces than the first letter of the plugin name.',
            },
        ]
    },
}


def render_config(config, template_renderer, notifier_name, _path=''):
    """
    Recurse through config data structures attempting to render any string fields against a given context.

    :param config: Any simple data structure as retrieved from the FlexGet config.
    :param template_renderer: A function that should take a string or Template argument, and return the result of
        rendering it with the appropriate context.
    :param notifier_name: This is used in log messages to let user know which notifier had a problem
        when there are rendering errors.
    """
    if isinstance(config, (str, Template)):
        try:
            return template_renderer(config)
        except Exception as e:
            logger.error(
                'Error rendering {} plugin config field `{}`: {}', notifier_name, config, e
            )
            logger.debug('{} notifier config location of error: {}', notifier_name, _path)
            return config
    elif isinstance(config, list):
        if _path:
            _path += '/'
        return [
            render_config(v, template_renderer, notifier_name, _path=_path + str(i))
            for i, v in enumerate(config)
        ]
    elif isinstance(config, dict):
        if _path:
            _path += '/'
        return {
            k: render_config(v, template_renderer, notifier_name, _path=_path + k)
            for k, v in config.items()
        }
    else:
        return config


class NotificationFramework:
    def send_notification(self, title, message, notifiers, template_renderer=None):
        """
        Send a notification out to the given `notifiers` with a given `title` and `message`.
        If `template_renderer` is specified, `title`, `message`, as well as any string options in a notifier's config
        will be rendered using this function before sending the message.

        :param str title: Title of the notification. (some notifiers may ignore this)
        :param str message: Main body of the notification.
        :param list notifiers: A list of configured notifier output plugins. The `NOTIFY_VIA_SCHEMA` JSON schema
            describes the data structure for this parameter.
        :param template_renderer: A function that should be used to render any jinja strings in the configuration.
        """
        if template_renderer:
            try:
                title = template_renderer(title)
            except RenderError as e:
                logger.error('Error rendering notification title: {}', e)
            try:
                message = template_renderer(message)
            except RenderError as e:
                logger.error('Error rendering notification body: {}', e)
        for notifier in notifiers:
            for notifier_name, notifier_config in notifier.items():
                notifier_plugin = plugin.get(notifier_name, self)

                rendered_config = notifier_config

                # If a template renderer is specified, try to render all the notifier config values
                if template_renderer:
                    rendered_config = render_config(
                        notifier_config, template_renderer, notifier_name
                    )

                logger.debug('Sending a notification to `{}`', notifier_name)
                try:
                    notifier_plugin.notify(
                        title, message, rendered_config
                    )  # TODO: Update notifiers for new api
                except PluginWarning as e:
                    logger.warning(
                        'Error while sending notification to `{}`: {}', notifier_name, e.value
                    )
                else:
                    logger.verbose('Successfully sent a notification to `{}`', notifier_name)


@event('plugin.register')
def register_plugin():
    plugin.register(NotificationFramework, 'notification_framework', api_ver=2, interfaces=[])
