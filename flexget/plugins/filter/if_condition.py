import datetime
from copy import copy

from jinja2 import UndefinedError
from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.task import Task
from flexget.utils.template import evaluate_expression

logger = logger.bind(name='if')


class FilterIf:
    """Can run actions on entries that satisfy a given condition.

    Actions include accept, reject, and fail, as well as the ability to run other filter plugins on the entries."""

    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'additionalProperties': {
                'anyOf': [{'$ref': '/schema/plugins'}, {'enum': ['accept', 'reject', 'fail']}]
            },
        },
    }

    def check_condition(self, condition, entry):
        """Checks if a given `entry` passes `condition`"""
        # Make entry fields and other utilities available in the eval namespace
        # We need our namespace to be an Entry instance for lazy loading to work
        eval_locals = copy(entry)
        eval_locals.update(
            {
                'has_field': lambda f: f in entry,
                'timedelta': datetime.timedelta,
                'utcnow': datetime.datetime.utcnow(),
                'now': datetime.datetime.now(),
            }
        )
        try:
            # Restrict eval namespace to have no globals and locals only from eval_locals
            passed = evaluate_expression(condition, eval_locals)
            if passed:
                logger.debug('{} matched requirement {}', entry['title'], condition)
            return passed
        except UndefinedError as e:
            # Extract the name that did not exist
            missing_field = e.args[0].split('\'')[1]
            logger.debug('{} does not contain the field {}', entry['title'], missing_field)
        except Exception as e:
            logger.error('Error occurred while evaluating statement `{}`. ({})', condition, e)

    def __getattr__(self, item):
        """Provides handlers for all phases."""
        for phase, method in plugin.phase_methods.items():
            if item == method and phase not in ['accept', 'reject', 'fail', 'input']:
                break
        else:
            raise AttributeError(item)

        def handle_phase(task, config):
            entry_actions = {'accept': Entry.accept, 'reject': Entry.reject, 'fail': Entry.fail}
            for item in config:
                requirement, action = list(item.items())[0]
                passed_entries = (e for e in task.entries if self.check_condition(requirement, e))
                if isinstance(action, str):
                    if not phase == 'filter':
                        continue
                    # Simple entry action (accept, reject or fail) was specified as a string
                    for entry in passed_entries:
                        entry_actions[action](entry, 'Matched requirement: %s' % requirement)
                else:
                    # Other plugins were specified to run on this entry
                    fake_task = Task(task.manager, task.name, config=action, options=task.options)
                    fake_task.session = task.session
                    # This entry still belongs to our feed, accept/reject etc. will carry through.
                    fake_task.all_entries[:] = passed_entries

                    methods = {}
                    for plugin_name, plugin_config in action.items():
                        p = plugin.get_plugin_by_name(plugin_name)
                        method = p.phase_handlers.get(phase)
                        if method:
                            methods[method] = (fake_task, plugin_config)
                    # Run the methods in priority order
                    for method in sorted(methods, reverse=True):
                        method(*methods[method])

        handle_phase.priority = 80
        return handle_phase


@event('plugin.register')
def register_plugin():
    plugin.register(FilterIf, 'if', api_ver=2)
