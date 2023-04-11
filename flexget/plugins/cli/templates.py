from flexget import options
from flexget.event import event
from flexget.terminal import TerminalTable, console, table_parser
from flexget.utils.template import get_template, list_templates


def list_file_templates(manager, options):
    header = [
        'Name',
        'Use with',
        TerminalTable.Column('Full Path', overflow='fold'),
        TerminalTable.Column('Contents', overflow='ignore'),
    ]
    table = TerminalTable(*header, table_type=options.table_type, show_lines=True)
    console('Fetching all file templates, stand by...')
    for template_name in list_templates(extensions=['template']):
        if options.name and options.name not in template_name:
            continue
        template = get_template(template_name)
        if 'entries' in template_name:
            plugin = 'notify_entries'
        elif 'task' in template_name:
            plugin = 'notify_task'
        else:
            plugin = '-'
        name = template_name.replace('.template', '').split('/')[-1]
        with open(template.filename) as contents:
            table.add_row(name, plugin, template.filename, contents.read().strip())

    console(table)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'templates',
        list_file_templates,
        help='View all available templates',
        parents=[table_parser],
    )
    parser.add_argument('--name', help='Filter results by template name')
