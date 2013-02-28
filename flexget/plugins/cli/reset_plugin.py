from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_parser_option
from flexget.event import event
from flexget.db_schema import reset_schema, plugin_schemas
from flexget.utils.tools import console

log = logging.getLogger('reset_plugin')


@event('manager.upgrade', priority=255)
def reset_plugin(manager):
    if not manager.options.reset_plugin:
        return
    manager.disable_tasks()
    plugin = manager.options.reset_plugin
    if plugin == '__list__':
        console('%-20s Ver Tables' % 'Name')
        console('-' * 79)
        for k, v in sorted(plugin_schemas.iteritems()):
            tables = ''
            line_len = 0
            for name in v['tables']:
                if line_len + len(name) + 2 >= 53:
                    tables += '\n'
                    tables += ' ' * 25
                    line_len = len(name) + 2
                else:
                    line_len += len(name) + 2
                tables += name + ', '
            tables = tables.rstrip(', ')
            console('%-20s %s   %s' % (k, v['version'], tables))
    else:
        try:
            reset_schema(plugin)
            console('The database for `%s` has been reset.' % plugin)
        except ValueError as e:
            console('Unable to reset %s: %s' % (plugin, e.message))


register_parser_option('--reset-plugin', action='store', nargs='?', dest='reset_plugin', const='__list__',
                       default=None, metavar='PLUGIN',
                       help='Reset the database for given PLUGIN. List known names without PLUGIN argument.')
