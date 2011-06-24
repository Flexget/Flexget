from sqlalchemy import ColumnDefault, Sequence
from sqlalchemy.types import AbstractType
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.exc import NoSuchTableError


def table_exists(name, session):
    """Hack, return True if table_name exists """

    try:
        meta = MetaData(bind=session.connection())
        Table(name, meta, autoload=True, autoload_with=session.connection())
    except NoSuchTableError:
        return False
    return True


def table_schema(name, session):
    """Hack, return table schema as it exists in the current db"""

    meta = MetaData(bind=session.bind, reflect=True)
    for table in meta.sorted_tables:
        if table.name == name:
            return table


def table_columns(table, session):
    """Returns list of columns in table or empty list

    Args:
        table: Name of table or table schema
    """

    res = []
    if isinstance(table, basestring):
        table = table_schema(table, session)
    for column in table.columns:
        res.append(column.name)
    return res


def table_add_column(table, name, col_type, session, default=None):
    """Adds a column to a table

    Args:
        table: Table to add column to (can be name or schema)
        name: Name of new column to add
        col_type: The sqlalchemy column type to add
        session: Session to do the alteration
        default: Default value for the created column (optional)
    """
    if isinstance(table, basestring):
        table = table_schema(table, session)
    if name in table_columns(table, session):
        # If the column already exists, we don't have to do anything.
        return
    # Add the column to the table
    if not isinstance(col_type, AbstractType):
        # If we got a type class instead of an instance of one, instantiate it
        col_type = col_type()
    type_string = session.bind.engine.dialect.type_compiler.process(col_type)
    statement = 'ALTER TABLE %s ADD %s %s' % (table.name, name, type_string)
    session.execute(statement)
    # Update the table with the default value if given
    if default is not None:
        # Get the new schema with added column
        table = table_schema(table.name, session)
        if not isinstance(default, (ColumnDefault, Sequence)):
            default = ColumnDefault(default)
        default._set_parent(table.c.added)
        statement = table.update().values({name: default.execute(bind=session.bind)})
        session.execute(statement)


def drop_tables(names, session):
    """Takes a list of table names and drops them from the database if they exist."""
    metadata = MetaData(bind=session.bind, reflect=True)
    for table in metadata.sorted_tables:
        if table.name in names:
            table.drop()
