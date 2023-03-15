from urllib.parse import quote

from loguru import logger
from rich.highlighter import ReprHighlighter
from rich.markup import escape
from rich.pretty import Pretty, is_expandable

from flexget import options, plugin
from flexget.event import event
from flexget.terminal import TerminalTable, console

logger = logger.bind(name='dump')


def dump(entries, debug=False, eval_lazy=False, trace=False, title_only=False):
    """
    Dump *entries* to stdout

    :param list entries: Entries to be dumped.
    :param bool debug: Print non printable fields as well.
    :param bool eval_lazy: Evaluate lazy fields.
    :param bool trace: Display trace information.
    :param bool title_only: Display only title field
    """

    def sort_key(field):
        # Sort certain fields above the rest
        if field == 'title':
            return (0,)
        if field == 'url':
            return (1,)
        if field == 'original_url':
            return (2,)
        return 3, field

    highlighter = ReprHighlighter()

    for entry in entries:
        entry_table = TerminalTable(
            'field',
            ':',
            'value',
            show_header=False,
            show_edge=False,
            pad_edge=False,
            collapse_padding=True,
            box=None,
            padding=0,
        )
        for field in sorted(entry, key=sort_key):
            if field.startswith('_') and not debug:
                continue
            if title_only and field != 'title':
                continue
            if entry.is_lazy(field) and not eval_lazy:
                renderable = (
                    '[italic]<LazyField - value will be determined when it is accessed>[/italic]'
                )
            else:
                try:
                    value = entry[field]
                except KeyError:
                    renderable = '[italic]<LazyField - lazy lookup failed>[/italic]'
                else:
                    if field.rsplit('_', maxsplit=1)[-1] == 'url':
                        url = quote(value, safe=":/")
                        renderable = f'[link={url}][repr.url]{escape(value)}[/repr.url][/link]'
                    elif isinstance(value, str):
                        renderable = escape(value.replace('\r', '').replace('\n', ''))
                    elif is_expandable(value):
                        renderable = Pretty(value)
                    else:
                        try:
                            renderable = highlighter(str(value))
                        except Exception:
                            renderable = f'[[i]not printable[/i]] ({repr(value)})'
            entry_table.add_row(f'{field}', ': ', renderable)
        console(entry_table)
        if trace:
            console('── Processing trace:', style='italic')
            trace_table = TerminalTable(
                'Plugin',
                'Operation',
                'Message',
                show_edge=False,
                pad_edge=False,
            )
            for item in entry.traces:
                trace_table.add_row(item[0], '' if item[1] is None else item[1], item[2])
            console(trace_table)
        if not title_only:
            console('')


class OutputDump:
    """
    Outputs all entries to console
    """

    schema = {'type': 'boolean'}

    @plugin.priority(0)
    def on_task_output(self, task, config):
        if not config and task.options.dump_entries is None:
            return

        eval_lazy = 'eval' in task.options.dump_entries
        trace = 'trace' in task.options.dump_entries
        title = 'title' in task.options.dump_entries
        states = {'accepted': 'green', 'rejected': 'red', 'failed': 'yellow', 'undecided': 'none'}
        dumpstates = [s for s in states if getattr(task, s)]
        specificstates = [s for s in states if s in task.options.dump_entries]
        if specificstates:
            dumpstates = specificstates
        for state in dumpstates:
            console.rule(state.title(), style=states[state])
            if getattr(task, state):
                dump(getattr(task, state), task.options.debug, eval_lazy, trace, title)
            else:
                console(f'No {state} entries', style='italic')
        if not dumpstates:
            console('No entries were produced', style='italic')


@event('plugin.register')
def register_plugin():
    plugin.register(OutputDump, 'dump', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--dump',
        nargs='*',
        choices=['eval', 'trace', 'accepted', 'rejected', 'undecided', 'failed', 'title'],
        dest='dump_entries',
        help=(
            'display all entries in task with fields they contain, '
            'use `--dump eval` to evaluate all lazy fields. Specify an entry '
            'state/states to only dump matching entries.'
        ),
    )
