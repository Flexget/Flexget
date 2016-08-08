from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import sys
from math import floor
from textwrap import wrap

from colorclass import Windows, Color
from flexget.options import ArgumentParser
from terminaltables import AsciiTable, SingleTable, DoubleTable, GithubFlavoredMarkdownTable
from terminaltables.terminal_io import terminal_size


class TerminalTable(object):
    """
    A data table suited for CLI output, created via its sent parameters.
    """

    def __init__(self, type, table_data, title=None, check_size=False):
        self.title = title
        self.type = type
        self.check_size = check_size
        self.table = self.supported_table_types()[type](table_data)

    @property
    def output(self):
        self.table.title = self.title
        if self.type == 'porcelain':
            # porcelain is a special case of AsciiTable
            self.table.inner_footing_row_border = False
            self.table.inner_heading_row_border = False
            self.table.outer_border = False
        if not self.check_size or self.table.ok:
            return '\n' + self.table.table
        raise CLITableError(
            'Terminal size is not suffice to display table. Terminal width is {}, table width is {}. '
            'Consider setting a lower value using `--max-width` option.'.format(terminal_size()[0],
                                                                                self.table.table_width))

    @staticmethod
    def supported_table_types(keys=False):
        """
        This method hold the dict for supported table type. Call with `keys=True` to get just the list of keys.
        """
        table_types = {
            'plain': AsciiTable,
            'porcelain': AsciiTable,
            'single': SingleTable,
            'double': DoubleTable,
            'github': GithubFlavoredMarkdownTable
        }
        if keys:
            return list(table_types)
        return table_types

    @staticmethod
    def word_wrap(text, max_length=0):
        """
        A helper method designed to return a wrapped string. This is a hack until (and if) `terminaltables` will support
        native word wrap.

        :param text: Text to wrap
        :param max_length: Maximum allowed string length, corresponds with column width when used with table
        :return: Wrapped text or original text
        """
        if max_length and len(str(text)) >= max_length:
            return '\n'.join(wrap(str(text), max_length))
        return text

    @staticmethod
    def table_truncate(table, num_of_columns, force_value=None):
        max_size = force_value or terminal_size()[0]
        # Maximum average column size equals the maximum size divided by number of columns subtracting 2
        #  spaces per column for padding
        max_col_size = floor(max_size / num_of_columns)
        output_table = []
        for row in table:
            output_row = []
            for value in row:
                output_value = str(value)[:max_col_size - 3] + '...' if len(str(value)) >= max_col_size else value
                output_row.append(output_value)
            output_table.append(output_row)
        return output_table


class CLITableError(Exception):
    """ A CLI table error"""


table_parser = ArgumentParser(add_help=False)
# The CLI table parent parser
table_parser.add_argument('--table-type', choices=TerminalTable.supported_table_types(keys=True), default='single',
                          help='Select output table style')
table_parser.add_argument('--porcelain', dest='table_type', action='store_const', const='porcelain',
                          help='Make the output parseable. Similar to using `--table-type porcelain`')
table_parser.add_argument('--max-width', dest='max_column_width', type=int, default=0,
                          help='Set the max allowed column width, will wrap any text longer than this value.'
                               ' Use this in case table size exceeds terminal size')
table_parser.add_argument('--check-size', action='store_true',
                          help='Only display table if it fits the current terminal size')


class Colorize(Color):
    """
    Inherited class from colorclass, tweaked some defaults for ease of use
    """

    @classmethod
    def colorize(cls, string, color, auto=True):
        if sys.platform == 'win32':
            Windows.enable(auto_colors=True)
        tag = '{0}{1}'.format('auto' if auto and 'auto' not in color else '', color)
        return cls('{%s}%s{/%s}' % (tag, string, tag))
