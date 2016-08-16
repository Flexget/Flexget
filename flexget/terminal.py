from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import sys
from textwrap import wrap

from colorclass import Windows, Color, disable_all_colors
from flexget.logger import local_context
from flexget.options import ArgumentParser
from flexget.utils.tools import io_encoding
from terminaltables import *
from terminaltables.terminal_io import terminal_size

# Enable terminal colors on windows
if sys.platform == 'win32':
    Windows.enable(auto_colors=True)


class TerminalTable(object):
    """A data table suited for CLI output, created via its sent parameters. For example::

        header = ['Col1', 'Col2']
        table_data = [header]
        for item in iterable:
            table_data.append([item.attribute1, item.attribute2])
        table = TerminalTable('plain', table_data)
        print table.output

    Optional values are setting table title, and supplying wrap_columns list. Each value in wrap_columns list is a tuple
    where first value is column number and second one is maximum column width. For example::

        header = ['Col1', 'Col2']
        table_data = [header]
        for item in iterable:
            table_data.append([item.attribute1, item.attribute2])
        table = TerminalTable('plain', table_data, 'Table title', wrap_columns=[(0,40),(1,50)])
        print table.output

    :param table_type: A string matching supported_table_types() keys.
    :param table_data: Table data as a list of lists of strings. See `terminaltables` doc.
    :param title: Optional title for table
    :param wrap_columns: A list of tuples which will be used to limit column size. First value in tuple should be column
     number, 2nd is maximum allowed size.
    """

    def __init__(self, table_type, table_data, title=None, wrap_columns=None):

        self.title = title
        self.type = table_type
        self.wrap_columns = wrap_columns
        self.table_data = table_data
        self.init_table()

    def init_table(self):
        """Assigns self.table with the built table based on data."""
        self.table = self.build_table(self.type, self.table_data)
        if not self.valid_table and not self.type == 'porcelain' and self.wrap_columns:
            self.table = self._wrap_table()

    def build_table(self, table_type, table_data):
        return self.supported_table_types()[table_type](table_data)

    @property
    def output(self):
        self.table.title = self.title
        if self.type == 'porcelain':
            # porcelain is a special case of AsciiTable
            self.table.inner_footing_row_border = False
            self.table.inner_heading_row_border = False
            self.table.outer_border = False
            disable_all_colors()
        return '\n' + self.table.table

    @staticmethod
    def supported_table_types():
        """This method hold the dict for supported table type."""
        return {
            'plain': AsciiTable,
            'porcelain': AsciiTable,
            'single': SingleTable,
            'double': DoubleTable,
            'github': GithubFlavoredMarkdownTable
        }

    @property
    def valid_table(self):
        return self.table.table_width <= terminal_size()[0]

    def _wrap_table(self):
        output_table = []
        for row in self.table_data:
            output_row = []
            for col_num, value in enumerate(row):
                output_value = value
                for col_limit in self.wrap_columns:
                    if col_num == col_limit[0]:
                        output_value = word_wrap(value, col_limit[1])
                output_row.append(output_value)
            output_table.append(output_row)
        return self.build_table(self.type, output_table)


class CLITableError(Exception):
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
    use case.
    :param color: Color tag to use
    :param text: Text to color
    :param auto: Whether to apply auto colors
    :return: Colored text
    """
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