from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.options import add_subparser
from flexget.db_schema import reset_schema, plugin_schemas
from flexget.utils.tools import console

log = logging.getLogger('reset_plugin')


def reset_plugin(manager, options):
    plugin = options.reset_plugin
    if not plugin:
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

parser = add_subparser('reset-plugin', reset_plugin, help='reset the database of a given plugin')
parser.add_argument('reset_plugin', metavar='<plugin>', nargs='?',
                    help='name of plugin to reset (if omitted, known plugins will be listed)')
