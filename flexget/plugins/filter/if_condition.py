from __future__ import unicode_literals, division, absolute_import
import __builtin__
import logging
import re
import datetime
from copy import copy

from flexget import plugin
from flexget.event import event
from flexget.task import Task
from flexget.entry import Entry

log = logging.getLogger('if')


def safer_eval(statement, locals):
    """A safer eval function. Does not allow __ or try statements, only includes certain 'safe' builtins."""
    allowed_builtins = ['True', 'False', 'str', 'unicode', 'int', 'float', 'len', 'any', 'all', 'sorted']
    for name in allowed_builtins:
        locals[name] = getattr(__builtin__, name)
    if re.search(r'__|try\s*:|lambda', statement):
        raise ValueError('`__`, lambda or try blocks not allowed in if statements.')
    return eval(statement, {'__builtins__': None}, locals)


class FilterIf(object):
    """Can run actions on entries that satisfy a given condition.

    Actions include accept, reject, and fail, as well as the ability to run other filter plugins on the entries."""

    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'additionalProperties': {
                'anyOf': [
                    {'$ref': '/schema/plugins'},
                    {'enum': ['accept', 'reject', 'fail']}
                ]
            }
        }
    }

    def check_condition(self, condition, entry):
        """Checks if a given `entry` passes `condition`"""
        # Make entry fields and other utilities available in the eval namespace
        # We need our namespace to be an Entry instance for lazy loading to work
        eval_locals = copy(entry)
        eval_locals.update({'has_field': lambda f: f in entry,
                            'timedelta': datetime.timedelta,
                            'now': datetime.datetime.now()})
        try:
            # Restrict eval namespace to have no globals and locals only from eval_locals
            passed = safer_eval(condition, eval_locals)
            if passed:
                log.debug('%s matched requirement %s' % (entry['title'], condition))
            return passed
        except NameError as e:
            # Extract the name that did not exist
            missing_field = e.args[0].split('\'')[1]
            log.debug('%s does not contain the field %s' % (entry['title'], missing_field))
        except Exception as e:
            log.error('Error occured while evaluating statement `%s`. (%s)' % (condition, e))

    def __getattr__(self, item):
        """Provides handlers for all phases."""
        for phase, method in plugin.phase_methods.iteritems():
            if item == method and phase not in ['accept', 'reject', 'fail', 'input']:
                break
        else:
            raise AttributeError(item)

        def handle_phase(task, config):
            entry_actions = {
                'accept': Entry.accept,
                'reject': Entry.reject,
                'fail': Entry.fail}
            for item in config:
                requirement, action = item.items()[0]
                passed_entries = [e for e in task.entries if self.check_condition(requirement, e)]
                if isinstance(action, basestring):
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
                    for plugin_name, plugin_config in action.iteritems():
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
