from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import sys
from math import floor
from textwrap import wrap

from colorclass import Windows, Color, disable_all_colors
from flexget.options import ArgumentParser
from terminaltables import AsciiTable, SingleTable, DoubleTable, GithubFlavoredMarkdownTable
from terminaltables.terminal_io import terminal_size


class TerminalTable(object):
    """
    A data table suited for CLI output, created via its sent parameters.

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
        """
        Build tables based on data. If table does not fit terminal, type is not porcelain and wrap_columns data has been
        passed, wrap table.
        :return: Mutate se
        """
        self.table = self.build_table(self.type, self.table_data)
        if not self.table.ok and not self.type == 'porcelain' and self.wrap_columns:
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
        """
        This method hold the dict for supported table type. Call with `keys=True` to get just the list of keys.
        """
        return {
            'plain': AsciiTable,
            'porcelain': AsciiTable,
            'single': SingleTable,
            'double': DoubleTable,
            'github': GithubFlavoredMarkdownTable
        }

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
# The CLI table parent parser
table_parser.add_argument('--table-type', choices=list(TerminalTable.supported_table_types()), default='single',
                          help='Select output table style')
table_parser.add_argument('--porcelain', dest='table_type', action='store_const', const='porcelain',
                          help='Make the output parseable. Similar to using `--table-type porcelain`')
table_parser.add_argument('--max-width', dest='max_column_width', type=int, default=0,
                          help='Set the max allowed column width, will wrap any text longer than this value.'
                               ' Use this in case table size exceeds terminal size')
table_parser.add_argument('--check-size', action='store_true',
                          help='Only display table if it fits the current terminal size')


def colorize(text, color, auto=True):
    """
    Helper function to color strings
    :param text: Text to color
    :param color: Color tag name
    :param auto: Wether to add `auto` to tag or not to use autocolors
    :return: Colorized string
    """
    if sys.platform == 'win32':
        Windows.enable(auto_colors=True)
    return Color.colorize(color, text, auto)


def word_wrap(text, max_length):
    """
    A helper method designed to return a wrapped string.

    :param text: Text to wrap
    :param max_length: Maximum allowed string length
    :return: Wrapped text or original text
    """
    if len(text) >= max_length:
        return '\n'.join(wrap(text, max_length))
    return text
