import contextlib
import os
import threading
from textwrap import wrap
from typing import Any, Iterator, Optional, TextIO, Union

import rich
import rich.box
import rich.console
import rich.rule
import rich.segment
import rich.table
import rich.text

from flexget.options import ArgumentParser

local_context = threading.local()


class _Console(rich.console.Console):
    def __init__(self, *args, **kwargs):
        if "PYCHARM_HOSTED" in os.environ:
            kwargs.setdefault('color_system', 'truecolor')
        kwargs.setdefault("markup", True)
        super().__init__(*args, **kwargs)

    def __call__(self, text: Any, *args, **kwargs) -> None:
        """
        Print to console safely. Output is able to be captured by different streams in different contexts.

        Any plugin wishing to output to the user's console should use this function instead of print so that
        output can be redirected when FlexGet is invoked from another process.

        Accepts arguments like the `rich.console.Console.print` function does.
        """
        self.print(text, *args, **kwargs)

    def print(self, *args, **kwargs) -> None:
        # Also capture calls directly to console.print
        _patchable_console(*args, **kwargs)

    def _print(self, *args, **kwargs):
        """The real parent print function, which can be called internally."""
        super().print(*args, **kwargs)

    def rule(
        self,
        title: rich.text.TextType = "",
        *,
        characters: str = "─",
        style: Union[str, rich.console.Style] = "rule.line",
        align: rich.text.AlignMethod = "left",
        # This is a custom FlexGet argument
        indent: int = 3,
    ) -> None:
        rule = rich.rule.Rule(title, characters=characters, style=style, align=align)
        if indent and title:
            if not isinstance(rule.title, rich.text.Text):
                rule.title = self.render_str(rule.title, style="rule.text")
            text = rich.text.Text()
            if rule.align == 'left':
                text = text.append(rule.characters * indent + ' ', style=rule.style)
            text.append(rule.title)
            if rule.align == 'right':
                text = text.append(' ' + rule.characters * indent, style=rule.style)
            rule.title = text
        self.print(rule)


# This is used to print (rich) text to the console, as well as expose all the other features of rich's console
# Unlike rich, can be called directly to print (for backwards compat purposes.)
console = _Console()


PORCELAIN_BOX: rich.box.Box = rich.box.Box(
    """\
    
  | 
    
  | 
    
    
  | 
    
""",
    ascii=True,
)

GITHUB_BOX: rich.box.Box = rich.box.Box(
    """\
    
| ||
|-||
| ||
|-||
|-||
| ||
    
""",
    ascii=True,
)


class TerminalTable(rich.table.Table):
    """
    A data table suited for CLI output, created via its sent parameters. For example::

        header = ['Col1', 'Col2']
        table_data = [header]
        for item in iterable:
            table_data.append([item.attribute1, item.attribute2])
        table = TerminalTable('plain', table_data)
        print table.output

    Optional values are setting table title, and supplying wrap_columns list and
    drop_column list. If table does not fit into terminal any columns listed in
    wrap_columns will be tried to wrap and if resulting columns are below MIN_WIDTH(10)
    columns listed in drop_column will be removed from output.

    Example::

        header = ['Col1', 'Col2']
        table_data = [header]
        for item in iterable:
            table_data.append([item.attribute1, item.attribute2])
        table = TerminalTable('plain', table_data, 'Table title', wrap_columns=[1,2],
                              drop_columns=[4,2])
        print table.output

    :param table_type: A string matching TABLE_TYPES keys.
    """

    # Easy access for our plugins without importing rich
    Column = rich.table.Column

    # TODO: Add other new types
    TABLE_TYPES = {
        'plain': {'box': rich.box.ASCII},
        'porcelain': {
            'box': PORCELAIN_BOX,
            'show_edge': False,
            'pad_edge': False,
            'title': None,
            'padding': 0,
        },
        'single': {'box': rich.box.SQUARE},
        'double': {'box': rich.box.DOUBLE},
        'github': {'box': GITHUB_BOX},
        'heavy-head': {'box': rich.box.HEAVY_HEAD},
    }

    def __init__(self, *args, table_type: Optional[str] = None, **kwargs) -> None:
        self.table_type = table_type
        if table_type:
            kwargs = {**kwargs, **self.TABLE_TYPES[table_type]}
        super().__init__(*args, **kwargs)

    def __rich_console__(self, console, options):
        segments = super().__rich_console__(console, options)
        if self.table_type not in ['porcelain', 'github']:
            yield from segments
            return
        # Strips out blank lines from our custom types
        lines = rich.segment.Segment.split_lines(segments)
        for line in lines:
            if any(seg.text.strip() for seg in line):
                yield from line
                yield rich.segment.Segment.line()


table_parser = ArgumentParser(add_help=False)
table_parser.add_argument(
    '--table-type',
    choices=list(TerminalTable.TABLE_TYPES),
    default='heavy-head',
    help='Select output table style',
)
table_parser.add_argument(
    '--porcelain',
    dest='table_type',
    action='store_const',
    const='porcelain',
    help='Make the output parseable. Similar to using `--table-type porcelain`',
)


def word_wrap(text: str, max_length: int) -> str:
    """A helper method designed to return a wrapped string.

    :param text: Text to wrap
    :param max_length: Maximum allowed string length
    :return: Wrapped text or original text
    """
    if len(text) >= max_length:
        return '\n'.join(wrap(text, max_length))
    return text


def colorize(color: str, text: str) -> str:
    """
    A simple override of Color.colorize which sets the default auto colors value to True, since it's the more common
    use case. When output isn't TTY just return text

    :param color: Color tag to use
    :param text: Text to color

    :return: Colored text or text
    """
    return f'[{color}]{text}[/]'


def disable_colors():
    """
    Disables colors to the terminal.
    """
    console.no_color = True


@contextlib.contextmanager
def capture_console(filelike: TextIO) -> Iterator:
    old_output = get_console_output()
    local_context.output = filelike
    try:
        yield
    finally:
        local_context.output = old_output


def get_console_output() -> Optional[TextIO]:
    return getattr(local_context, 'output', None)


def _patchable_console(*args, **kwargs):
    # Nobody will import this directly, so we can monkeypatch it for IPC calls
    console.file = get_console_output()
    try:
        console._print(*args, **kwargs)
    finally:
        console.file = None
