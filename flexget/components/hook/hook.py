from loguru import logger

from flexget import plugin
from flexget.task import Task
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.components.hook.hook_util import ENDPOINT, task_to_dict


PLUGIN_NAME = 'hook'
logger = logger.bind(name=PLUGIN_NAME)


class Hook:
    """
    Sends a Hook

    Config:
    hook:
      title: <<title | optional>>
      events <<events to lisen [task|phase|plugin] optional>>
      stages <<stages to lisen [start|end] optional>>
      tasks  <<tasks to lisen optional>>
      plugins <<plugins to lisen optional>>
      when <<when to trigger [accepted|rejected|failed|no_entries|aborted] optional
      phases <<phases to lisen>>
      via
        - <<hook interfaxe>>

    Example:
      hook:
        - events:
            - phase
            - plugin
          when: accepted
          via:
            - webhooks:
                host: 'https://noderedurl.1880'
                method: 'get'
                endpoint: 'flexget/{{event_tree|join('/')}}'
                data:
                  task: '{{task_name}}'

    """

    config = {}

    schema = one_or_more(
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'title': {'type': 'string'},
                'events': one_or_more(
                    {
                        'type': 'string',
                        'enum': ['task', 'phase', 'plugin'],
                    }
                ),
                'stages': one_or_more({'type': 'string', 'enum': ['start', 'end']}),
                'tasks': one_or_more({'type': 'string'}),
                'plugins': one_or_more({'type': 'string'}),
                'when': one_or_more(
                    {
                        'type': 'string',
                        'enum': [
                            'accepted',
                            'rejected',
                            'failed',
                            'no_entries',
                            'aborted',
                        ],
                    }
                ),
                'phases': one_or_more(
                    {
                        'type': 'string',
                        'enum': plugin.task_phases,
                    }
                ),
                'via': {
                    'type': 'array',
                    'items': {
                        'allOf': [
                            {'$ref': '/schema/plugins?interface=hooks'},
                            {
                                'maxProperties': 1,
                                'error_maxProperties': 'Plugin options indented 2 more spaces than '
                                'the first letter of the plugin name.',
                                'minProperties': 1,
                            },
                        ]
                    },
                },
            },
        }
    )

    @staticmethod
    def send_hook(title, data: dict, hooks, *args, **kwargs):
        hooks_run = []
        for hook in hooks:
            if Hook.check_run_hook(hook, data, **kwargs):
                hooks_run.append(hook)

        if not hooks_run:
            return

        send_hook = plugin.get_plugin_by_name('hook_framework').instance.send_hook
        send_hook(title, data, hooks, *args, **kwargs)

    @staticmethod
    def set_config(task: Task, configs: dict):
        if configs is None:
            configs = []
        elif not isinstance(configs, list):
            configs = [configs]

        for config in configs:
            events = config.get('events', [])
            events = events if isinstance(events, list) else [events]
            config['events'] = events

            stages = config.get('stages', [])
            stages = stages if isinstance(stages, list) else [stages]
            config['stages'] = stages

            tasks = config.get('tasks', [])
            tasks = tasks if isinstance(tasks, list) else [tasks]
            config['tasks'] = tasks

            plugins = config.get('plugins', [])
            plugins = plugins if isinstance(plugins, list) else [plugins]
            config['plugins'] = plugins

            when = config.get('when', [])
            when = when if isinstance(when, list) else [when]
            config['when'] = when

            phases = config.get('phases', [])
            phases = phases if isinstance(phases, list) else [phases]
            config['phases'] = phases

            via = config.get('via', [])
            via = via if isinstance(via, list) else [via]
            config['via'] = via

        Hook.config[task.id] = configs

    @staticmethod
    def get_config(task: Task):
        if Hook.config is None or not task.id in Hook.config:
            return None

        return Hook.config[task.id]

    @staticmethod
    def delete_config(task: Task):
        if Hook.config is None or not task.id in Hook.config:
            return

        del Hook.config[task.id]

    @staticmethod
    def _is_builtins(plugin_check):
        return plugin.plugins[plugin_check].builtin

    # First Tasks
    def on_task_prepare(self, task, config):
        Hook.set_config(task, config)
        Hook.on_phase_ended(task, task.current_phase)

    def on_task_start(self, task, config):
        Hook.set_config(task, config)
        Hook.on_task_started(task)

    @event('task.execute.started')
    def on_task_started(self):
        config = Hook.get_config(self)
        if not config:
            return

        Hook.send_hook(
            None,
            task_to_dict(self),
            config,
            event=ENDPOINT['EVENT_TASK'],
            stage=ENDPOINT['STAGE_START'],
            name=getattr(self, 'name'),
            task=self,
        )

    @event('task.execute.completed')
    def on_task_end(self):
        config = Hook.get_config(self)
        Hook.delete_config(self)
        if not config:
            return

        Hook.send_hook(
            None,
            task_to_dict(self),
            config,
            event=ENDPOINT['EVENT_TASK'],
            stage=ENDPOINT['STAGE_END'],
            name=getattr(self, 'name'),
            task=self,
        )

    @event('task.execute.before_plugin')
    def on_plugin_started(self, plugin_e):
        config = Hook.get_config(self)
        if not config:
            return

        if Hook._is_builtins(plugin_e):
            return

        Hook.send_hook(
            None,
            task_to_dict(self),
            config,
            evet=ENDPOINT['EVENT_PLUGIN'],
            stage=ENDPOINT['STAGE_START'],
            name=plugin_e,
            task=self,
        )

    @event('task.execute.after_plugin')
    def on_plugin_ended(self, plugin_e):
        config = Hook.get_config(self)
        if not config:
            return

        if Hook._is_builtins(plugin_e):
            return

        Hook.send_hook(
            None,
            task_to_dict(self),
            config,
            event=ENDPOINT['EVENT_PLUGIN'],
            stage=ENDPOINT['STAGE_END'],
            name=plugin_e,
            task=self,
        )

    @event('task.execute.before_phase')
    def on_phase_started(self, phase_e):
        config = Hook.get_config(self)
        if not config:
            return

        Hook.send_hook(
            None,
            task_to_dict(self),
            config,
            event=ENDPOINT['EVENT_PHASE'],
            stage=ENDPOINT['STAGE_START'],
            name=phase_e,
            task=self,
        )

    @event('task.execute.after_phase')
    def on_phase_ended(self, phase_e):
        config = Hook.get_config(self)
        if not config:
            return

        Hook.send_hook(
            None,
            task_to_dict(self),
            config,
            event=ENDPOINT['EVENT_PHASE'],
            stage=ENDPOINT['STAGE_END'],
            name=phase_e,
            task=self,
        )

    @staticmethod
    def check_run_hook(config: dict, data: dict, **keyarg) -> bool:
        if not config:
            return False

        event_name = keyarg.get('event', 'unkown')
        stage_name = keyarg.get('stage', 'unkown')
        name = keyarg.get('name', 'unkown')

        task_name = 'unkwon'
        if 'task' in keyarg:
            task_name = keyarg.get('task').name
        elif event_name == ENDPOINT['EVENT_TASK']:
            task_name = name

        config_tasks = config.get('tasks')
        config_event = config.get('events')
        config_stage = config.get('stages')
        config_phases = config.get('phases')
        config_plugins = config.get('plugins')
        config_when = config.get('when')

        conditions = [
            data.get('accepted') and 'accepted' in config_when,
            data.get('rejected') and 'rejected' in config_when,
            data.get('failed') and 'failed' in config_when,
            data.get('aborted') and 'aborted' in config_when,
            not data.get('all_entries') and 'no_entries' in config_when,
        ]
        if not any(conditions):
            return False

        if config_event and event_name not in config_event:
            return False

        if config_stage and stage_name not in config_stage:
            return False

        if config_tasks and task_name not in config_tasks:
            return False

        if event_name == ENDPOINT['EVENT_PHASE'] and config_phases and name not in config_phases:
            return False

        if (
            event_name == ENDPOINT['EVENT_PLUGIN']
            and config_plugins
            and name not in config_plugins
        ):
            return False

        return True


@event('plugin.register')
def register_plugin():
    plugin.register(Hook, PLUGIN_NAME, api_ver=2)
