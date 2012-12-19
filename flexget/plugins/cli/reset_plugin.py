import logging
from flexget.plugin import register_parser_option
from flexget.event import event
from flexget.schema import reset_schema
from flexget.utils.tools import console

log = logging.getLogger('reset_plugin')


@event('manager.upgrade', priority=255)
def reset_plugin(manager):
    if not manager.options.reset_plugin:
        return
    manager.disable_tasks()
    plugin = manager.options.reset_plugin
    try:
        reset_schema(plugin)
        console('The database for `%s` has been reset.' % plugin)
    except ValueError as e:
        console('Unable to reset %s: %s' % (plugin, e.message))


register_parser_option('--reset-plugin', action='store', dest='reset_plugin', default=None,
                       metavar='PLUGIN', help='Reset the database for given PLUGIN')
