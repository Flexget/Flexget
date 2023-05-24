from flexget import options, plugin
from flexget.event import event
from flexget.manager import Manager
from flexget.terminal import TerminalTable, console, table_parser
from flexget.utils.database import with_session

from . import db

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.imdb.utils import extract_id, is_imdb_url
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='imdb')


def do_cli(manager, options):
    if options.seen_action == 'forget':
        seen_forget(manager, options)
    elif options.seen_action == 'add':
        seen_add(manager, options)
    elif options.seen_action == 'search':
        seen_search(manager, options)


def seen_forget(manager: Manager, options):
    forget_name = options.forget_value
    if is_imdb_url(forget_name):
        imdb_id = extract_id(forget_name)
        if imdb_id:
            forget_name = imdb_id

    tasks = None
    if options.tasks:
        tasks = []
        for task in options.tasks:
            try:
                tasks.extend(m for m in manager.matching_tasks(task) if m not in tasks)
            except ValueError as e:
                console(e)
                continue

    # If tasks are specified it should use pattern matching as search
    if tasks:
        forget_name = forget_name.replace("%", "\\%").replace("_", "\\_")
        forget_name = forget_name.replace("*", "%").replace("?", "_")

    count, fcount = db.forget(forget_name, tasks=tasks, test=options.test)
    console(f'Removed {count} titles ({fcount} fields)')
    manager.config_changed()


def seen_add(manager: Manager, options):
    DEFAULT_TASK = 'cli_add'

    seen_name = options.add_value
    if is_imdb_url(seen_name):
        console('IMDB url detected, try to parse ID')
        imdb_id = extract_id(seen_name)
        if imdb_id:
            seen_name = imdb_id
        else:
            console("Could not parse IMDB ID")

    task = DEFAULT_TASK
    local = None
    if options.task and options.task not in manager.tasks:
        console(f"Task `{options.task}` not in config")
        return
    else:
        task = options.task
        local = True

    db.add(seen_name, task, {'cli_add': seen_name}, local=local)

    if task == DEFAULT_TASK:
        console(f'Added `{seen_name}` as seen. This will affect all tasks.')
    else:
        console(f'Added `{seen_name}` as seen. This will affect `{task}` task.')


@with_session
def seen_search(manager: Manager, options, session=None):
    search_term = options.search_term
    if is_imdb_url(search_term):
        console('IMDB url detected, parsing ID')
        imdb_id = extract_id(search_term)
        if imdb_id:
            search_term = imdb_id
        else:
            console("Could not parse IMDB ID")
    else:
        search_term = search_term.replace("%", "\\%").replace("_", "\\_")
        search_term = search_term.replace("*", "%").replace("?", "_")

    tasks = None
    if options.tasks:
        tasks = []
        for task in options.tasks:
            try:
                tasks.extend(m for m in manager.matching_tasks(task) if m not in tasks)
            except ValueError as e:
                console(e)
                continue

    seen_entries = db.search(value=search_term, status=None, tasks=tasks, session=session)
    table = TerminalTable('Field', 'Value', table_type=options.table_type)
    for se in seen_entries.all():
        table.add_row('Title', se.title)
        for sf in se.fields:
            if sf.field.lower() == 'title':
                continue
            table.add_row(f'{sf.field.upper()}', str(sf.value))
        table.add_row('Task', se.task)
        if se.local:
            table.add_row('Local', 'Yes')
        table.add_row('Added', se.added.strftime('%Y-%m-%d %H:%M'), end_section=True)
    if not table.rows:
        console('No results found for search')
        return
    console(table)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'seen', do_cli, help='View or forget entries remembered by the seen plugin'
    )
    subparsers = parser.add_subparsers(dest='seen_action', metavar='<action>')
    forget_parser = subparsers.add_parser(
        'forget', help='Forget entry or entire task from seen plugin database'
    )
    forget_parser.add_argument(
        '--tasks',
        nargs='+',
        metavar='TASK',
        help='forget only in specified task(s), optionally using glob patterns ("tv-*"). '
        'matching is case-insensitive',
    )

    forget_parser.add_argument(
        'forget_value',
        metavar='<value>',
        help='Title or url of entry to forget, or name of task to forget',
    )
    add_parser = subparsers.add_parser('add', help='Add a title or url to the seen database')
    add_parser.add_argument(
        '--task',
        metavar='TASK',
        help='add in specified task'
        'matching is case-insensitive. Will make entry local to that task',
    )
    add_parser.add_argument('add_value', metavar='<value>', help='the title or url to add')
    search_parser = subparsers.add_parser(
        'search', help='Search text from the seen database', parents=[table_parser]
    )
    search_parser.add_argument(
        '--tasks',
        nargs='+',
        metavar='TASK',
        help='search only in specified task(s), optionally using glob patterns ("tv-*"). '
        'matching is case-insensitive',
    )
    search_parser.add_argument('search_term', metavar='<search term>')
