"""
This plugin adds a notification hook which can be used by other plugins to send hooks,
via a transport service configurable by the user.
Sending Messages
----------------
A plugin who wishes to send messages using this hook framework should import this plugin, then call the
`send_hook` method. Example::
    from flexget import plugin
    send_notification = plugin.get_plugin_by_name('hook_framework').instance.send_hook
    send_notification('the title', 'the data', the_hoks)
Delivering Messages
-------------------
To implement a plugin that can deliver messages, it should implement a `send_hook` method, which takes
`(title, data, config)` as arguments. The plugin should also have a `schema` attribute which is a JSON schema that
describes the config format for the plugin.
"""

from typing import Union
from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import DependencyError
from flexget.components.hook.hook_util import jsonify
from flexget.utils.template import render, FlexGetTemplate
from flexget.components.notify.notification_framework import render_config

PLUGIN_NAME = 'hook_framework'
logger = logger.bind(name=PLUGIN_NAME)


class HookHolder:
    """
    Hook Holder for template generator
    """

    _data = {}

    def __init__(self, data):
        self._data = data

    def template_renderer(self, template: Union[str, FlexGetTemplate]):
        return render(template, self._data, False)


class HookFramework:
    @staticmethod
    def render_config(config, data, plugin_name):
        holder = HookHolder(data)
        new_config = render_config(config, holder.template_renderer, plugin_name)
        return new_config

    @staticmethod
    def send_hook(title, data: dict, hooks, **kwargs):
        """
        Send a hook out to the given `hook` with a given `title` and `data`.
        :param str title: Title of the hook. (some hooks may ignore this)
        :param str|dict data: Main data of the hook.
        :param list hooks: A list of configured hooks output plugins.
        """

        send_data = {**data}

        # Get Key Arguments
        event_match = {}
        if kwargs:
            event_match['event'] = kwargs.get('event')
            event_match['name'] = kwargs.get('name')
            event_match['stage'] = kwargs.get('stage')

        if title:
            send_data['title'] = title

        if event_match:
            send_data['event_type'] = event_match.get('event')
            send_data['event_name'] = event_match.get('name')
            send_data['event_stage'] = event_match.get('stage')

            send_data['event_tree'] = []
            for eve in event_match:
                send_data['event_tree'].append(event_match[eve])

        if isinstance(hooks, str):
            hooks = [{'via': {hooks: {}}}]
        elif isinstance(hooks, dict) and 'via' not in hooks:
            hooks = [{'via': {**hooks}}]
        elif isinstance(hooks, dict):
            hooks = [hooks]

        for hook in hooks:
            if 'via' not in hook:
                logger.error('Hook informed with wrong schema, missing via')
                continue

            hook_via = hook['via']
            if not isinstance(hook_via, list):
                hook_via = [hook_via]

            for plugin_hook in hook_via:
                if len(list(plugin_hook.keys())) != 1:
                    logger.error('Hook informed with wrong schema, invalid plugin name')
                    continue

                plugin_name = list(plugin_hook.keys())[0]
                if not isinstance(plugin_name, str):
                    logger.error('Hook informed with wrong schema, invalid plugin name')
                    continue

                if plugin_name not in plugin_hook:
                    logger.error('Hook informed with wrong schema, no config for {}', plugin_name)
                    continue

                plugin_config = plugin_hook[plugin_name]

                if not isinstance(plugin_config, dict):
                    logger.error('Hook informed with wrong schema, no config for {}', plugin_name)
                    continue

                send_data = jsonify(send_data)

                template_data = {**send_data}
                template_data['data'] = {**send_data}

                new_config = HookFramework.render_config(plugin_config, send_data, plugin_name)

                HookFramework.trigger_hook(
                    plugin_name, title=title, data=send_data, config=new_config
                )

    @staticmethod
    def trigger_hook(plugin_name, **kwargs):

        try:
            hook_plugin = plugin.get(plugin_name, HookFramework).send_hook
        except DependencyError as error:
            logger.error('Invalid plugin \'{}\'', plugin_name)
            return

        try:
            hook_plugin(**kwargs)
        except plugin.PluginError as error:
            logger.error(error)
        except plugin.PluginWarning as error:
            logger.warning(error)
        except Exception as error:
            logger.exception(error)


@event('plugin.register')
def register_plugin():
    plugin.register(HookFramework, PLUGIN_NAME, api_ver=2, interfaces=[])
