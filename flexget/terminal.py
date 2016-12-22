from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import sys
from textwrap import wrap

from colorclass import Windows, Color
from flexget.logger import local_context
from flexget.options import ArgumentParser
from flexget.utils.tools import io_encoding
from terminaltables import AsciiTable, SingleTable, DoubleTable, GithubFlavoredMarkdownTable, PorcelainTable
from terminaltables.terminal_io import terminal_size

# Enable terminal colors on windows.
# pythonw (flexget-headless) does not have a sys.stdout, this command would crash in that case
if sys.platform == 'win32' and sys.stdout:
    Windows.enable(auto_colors=True)


def terminal_info():
    """
    Returns info we need about the output terminal.
    When called over IPC, this function is monkeypatched to return the info about the client terminal.
    """
    return {'size': terminal_size(), 'isatty': sys.stdout.isatty()}


class TerminalTable(object):
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

    :param table_type: A string matching supported_table_types() keys.
    :param table_data: Table data as a list of lists of strings. See `terminaltables` doc.
    :param title: Optional title for table
    :param wrap_columns: A list of column numbers which will can be wrapped.
        In case of multiple values even split is used.
    :param drop_columns: A list of column numbers which can be dropped if needed.
        List in order of priority.
    """

    MIN_WIDTH = 10
    ASCII_TYPES = ['plain', 'porcelain']

    def __init__(self, table_type, table_data, title=None, wrap_columns=None, drop_columns=None):
        self.title = title
        self.wrap_columns = wrap_columns or []
        self.drop_columns = drop_columns or []
        self.table_data = table_data

        # Force table type to be ASCII when not TTY and type isn't already ASCII
        if table_type not in self.ASCII_TYPES and not terminal_info()['isatty']:
            self.type = 'porcelain'
        else:
            self.type = table_type

        self.init_table()

    def init_table(self):
        """Assigns self.table with the built table based on data."""
        self.table = self.build_table(self.type, self.table_data)
        if self.type == 'porcelain':
            return
        adjustable = bool(self.wrap_columns + self.drop_columns)
        if not self.valid_table and adjustable:
            self.table = self._resize_table()

    def build_table(self, table_type, table_data):
        return self.supported_table_types()[table_type](table_data)

    @property
    def output(self):
        self.table.title = self.title
        return '\n' + self.table.table

    @staticmethod
    def supported_table_types():
        """This method hold the dict for supported table type."""
        return {
            'plain': AsciiTable,
            'porcelain': PorcelainTable,
            'single': SingleTable,
            'double': DoubleTable,
            'github': GithubFlavoredMarkdownTable
        }

    @property
    def _columns(self):
        if not self.table_data:
            return 0
        else:
            return len(self.table_data[0])

    def _longest_rows(self):
        """
        Calculate longest line for each column.

        :returns: dictionary where key is column number and value longest value
        """
        longest = {c: 0 for c in range(self._columns)}
        for row in self.table_data:
            for index, value in enumerate(row):
                if len(str(value)) > longest[index]:
                    longest[index] = len(str(value))
        return longest

    @property
    def valid_table(self):
        # print('self.table.table_width: %s' % self.table.table_width)
        # print('terminal_size()[0]: %s' % terminal_size()[0])
        return self.table.table_width <= terminal_info()['size'][0]

    def _calc_wrap(self):
        """
        :return: Calculated wrap value to be used for self.wrap_columns.
            If wraps are not defined None is returned
        """
        if not self.wrap_columns:
            return None
        longest = self._longest_rows()
        margin = self._columns * 2 + self._columns + 1
        static_columns = sum(longest.values())
        for wrap_c in self.wrap_columns:
            static_columns -= longest[wrap_c]
        space_left = terminal_info()['size'][0] - static_columns - margin
        # TODO: This is a bit dumb if wrapped columns have huge disparity
        # for example in flexget plugins the phases and flags
        return int(space_left / len(self.wrap_columns))

    def _drop_column(self, col):
        name = self.table_data[0][col]
        console('Least important column `%s` removed due terminal size' % name)

        for row in self.table_data:
            del row[col]

        def adjust(l):
            new_vals = []
            for c in l:
                if c == col:
                    # column removed
                    continue
                if c > col:
                    # column before removed
                    new_vals.append(c - 1)
                else:
                    new_vals.append(c)
            return new_vals

        self.wrap_columns = adjust(self.wrap_columns)
        self.drop_columns = adjust(self.drop_columns)

    def _drop_columns_with_wrap(self):
        """Drop columns until wrapped columns fit or are removed as well"""
        while self.drop_columns and self.wrap_columns:
            drop = self.drop_columns.pop(0)
            self._drop_column(drop)
            wrapped_width = self._calc_wrap()
            if wrapped_width < self.MIN_WIDTH:
                continue
            else:
                return

    def _resize_table(self):
        """Adjust table data and columns to fit into terminal"""
        if self.drop_columns and not self.wrap_columns:
            while self.drop_columns and not self.valid_table:
                drop = self.drop_columns.pop(0)
                self._drop_column(drop)

        wrapped_width = self._calc_wrap()
        if wrapped_width and wrapped_width < self.MIN_WIDTH:
            self._drop_columns_with_wrap()
            wrapped_width = self._calc_wrap()

        # construct new table
        output_table = []
        for row in self.table_data:
            output_row = []
            for col_num, value in enumerate(row):
                output_value = value
                if col_num in self.wrap_columns:
                    # This probably shouldn't happen, can be caused by wrong parameters sent to drop_columns and
                    # wrap_columns
                    if wrapped_width <= 0:
                        raise TerminalTableError('Table could not be rendered correctly using it given data')
                    output_value = word_wrap(str(value), wrapped_width)
                output_row.append(output_value)
            output_table.append(output_row)
        return self.build_table(self.type, output_table)


class TerminalTableError(Exception):
    """ A CLI table error"""


table_parser = ArgumentParser(add_help=False)
table_parser.add_argument('--table-type', choices=list(TerminalTable.supported_table_types()), default='single',
                          help='Select output table style')
table_parser.add_argument('--porcelain', dest='table_type', action='store_const', const='porcelain',
                          help='Make the output parseable. Similar to using `--table-type porcelain`')


def word_wrap(text, max_length):
    """A helper method designed to return a wrapped string.

    :param text: Text to wrap
    :param max_length: Maximum allowed string length
    :return: Wrapped text or original text
    """
    if len(text) >= max_length:
        return '\n'.join(wrap(text, max_length))
    return text


def colorize(color, text, auto=True):
    """
    A simple override of Color.colorize which sets the default auto colors value to True, since it's the more common
    use case. When output isn't TTY just return text

    :param color: Color tag to use
    :param text: Text to color
    :param auto: Whether to apply auto colors

    :return: Colored text or text
    """
    if not terminal_info()['isatty']:
        return text
    return Color.colorize(color, text, auto)


def console(text, *args, **kwargs):
    """
    Print to console safely. Output is able to be captured by different streams in different contexts.

    Any plugin wishing to output to the user's console should use this function instead of print so that
    output can be redirected when FlexGet is invoked from another process.

    Accepts arguments like the `print` function does.
    """
    kwargs['file'] = getattr(local_context, 'output', sys.stdout)
    try:
        print(text, *args, **kwargs)
    except UnicodeEncodeError:
        text = text.encode(io_encoding, 'replace').decode(io_encoding)
        print(text, *args, **kwargs)
    kwargs['file'].flush()  # flush to make sure the output is printed right away
