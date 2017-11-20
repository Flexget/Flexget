"""
Miscellaneous SQLAlchemy helpers.
"""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

import sqlalchemy

from sqlalchemy import ColumnDefault, Sequence, Index
from sqlalchemy.types import TypeEngine
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.exc import NoSuchTableError, OperationalError

log = logging.getLogger('sql_utils')


def table_exists(name, session):
    """
    Use SQLAlchemy reflect to check table existences.

    :param string name: Table name to check
    :param Session session: Session to use
    :return: True if table exists, False otherwise
    :rtype: bool
    """
    try:
        table_schema(name, session)
    except NoSuchTableError:
        return False
    return True


def table_schema(name, session):
    """
    :returns: Table schema using SQLAlchemy reflect as it currently exists in the db
    :rtype: Table
    """
    return Table(name, MetaData(bind=session.bind), autoload=True)


def table_columns(table, session):
    """
    :param string table: Name of table or table schema
    :param Session session: SQLAlchemy Session
    :returns: List of column names in the table or empty list
    """

    res = []
    if isinstance(table, basestring):
        table = table_schema(table, session)
    for column in table.columns:
        res.append(column.name)
    return res


def table_add_column(table, name, col_type, session, default=None):
    """Adds a column to a table

    .. warning:: Uses raw statements, probably needs to be changed in
                 order to work on other databases besides SQLite

    :param string table: Table to add column to (can be name or schema)
    :param string name: Name of new column to add
    :param col_type: The sqlalchemy column type to add
    :param Session session: SQLAlchemy Session to do the alteration
    :param default: Default value for the created column (optional)
    """
    if isinstance(table, basestring):
        table = table_schema(table, session)
    if name in table_columns(table, session):
        # If the column already exists, we don't have to do anything.
        return
    # Add the column to the table
    if not isinstance(col_type, TypeEngine):
        # If we got a type class instead of an instance of one, instantiate it
        col_type = col_type()
    type_string = session.bind.engine.dialect.type_compiler.process(col_type)
    statement = 'ALTER TABLE %s ADD %s %s' % (table.name, name, type_string)
    session.execute(statement)
    session.commit()
    # Update the table with the default value if given
    if default is not None:
        # Get the new schema with added column
        table = table_schema(table.name, session)
        if not isinstance(default, (ColumnDefault, Sequence)):
            default = ColumnDefault(default)
        default._set_parent(getattr(table.c, name))
        statement = table.update().values({name: default.execute(bind=session.bind)})
        session.execute(statement)
        session.commit()


def drop_tables(names, session):
    """Takes a list of table names and drops them from the database if they exist."""
    metadata = MetaData()
    metadata.reflect(bind=session.bind)
    for table in metadata.sorted_tables:
        if table.name in names:
            table.drop()


def get_index_by_name(table, name):
    """
    Find declaratively defined index from table by name

    :param table: Table object
    :param string name: Name of the index to get
    :return: Index object
    """
    for index in table.indexes:
        if index.name == name:
            return index


def create_index(table_name, session, *column_names):
    """
    Creates an index on specified `columns` in `table_name`

    :param table_name: Name of table to create the index on.
    :param session: Session object which should be used
    :param column_names: The names of the columns that should belong to this index.
    """
    index_name = '_'.join(['ix', table_name] + list(column_names))
    table = table_schema(table_name, session)
    columns = [getattr(table.c, column) for column in column_names]
    try:
        Index(index_name, *columns).create(bind=session.bind)
    except OperationalError:
        log.debug('Error creating index.', exc_info=True)


class ContextSession(sqlalchemy.orm.Session):
    """:class:`sqlalchemy.orm.Session` which can be used as context manager"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
