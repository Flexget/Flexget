from loguru import logger

from flexget import plugin
from flexget.entry import register_lazy_lookup
from flexget.event import event
from flexget.utils.template import RenderError

logger = logger.bind(name='set')

# Use a string for this sentinel, so it survives serialization
UNSET = '__unset__'


class ModifySet:
    """Allows adding information to a task entry for use later.

    Example:

    set:
      path: ~/download/path/
    """

    schema = {'type': 'object', "minProperties": 1}

    def on_task_metainfo(self, task, config):
        """Adds the set dict to all accepted entries."""
        for entry in task.all_entries:
            self.modify(entry, config)

    def modify(self, entry, config, errors=True):
        """This can be called from a plugin to add set values to an entry"""
        for field in config:
            # If this doesn't appear to be a jinja template, just set it right away.
            if not isinstance(config[field], str) or '{' not in config[field]:
                entry[field] = config[field]
            # Store original values before overwriting with a lazy field, so that set directives can reference
            # themselves.
            else:
                orig_value = entry.get(field, UNSET, eval_lazy=False)
                try:
                    del entry[field]
                except KeyError:
                    pass
                entry.add_lazy_fields(
                    self.lazy_set,
                    [field],
                    kwargs={
                        'config': config,
                        'field': field,
                        'orig_field_value': orig_value,
                        'errors': errors,
                    },
                )

    @register_lazy_lookup('set_field')
    def lazy_set(self, entry, config, field, orig_field_value, errors=True):
        level = 'ERROR' if errors else 'DEBUG'
        if orig_field_value is not UNSET:
            entry[field] = orig_field_value
        try:
            entry[field] = entry.render(config[field], native=True)
        except RenderError as e:
            logger.log(level, 'Could not set {} for {}: {}', field, entry['title'], e)


@event('plugin.register')
def register_plugin():
    plugin.register(ModifySet, 'set', api_ver=2)
