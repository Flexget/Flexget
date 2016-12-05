from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa

import io

from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console
from flexget import options
from flexget.event import event
from flexget.utils.template import list_templates, get_template


def list_file_templates(manager, options):
    header = ['Name', 'Full Path', 'Contents']
    table_data = [header]
    console('Fetching all file templates, stand by...')
    for template_name in list_templates(extensions=['template']):
        if options.name and not options.name in template_name:
            continue
        template = get_template(template_name)
        with io.open(template.filename) as contents:
            table_data.append([template_name, template.filename, contents.read()])

    try:
        table = TerminalTable(options.table_type, table_data, wrap_columns=[1, 2], drop_columns=[1])
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))
    else:
        console(table.output)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('templates', list_file_templates, help='View all available templates',
                                      parents=[table_parser])
    parser.add_argument('--name', help='Filter results by template name')
