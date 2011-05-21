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


def table_columns(name, session):
    """
    :name: Name of the table

    Returns list of columns in table or empty list
    """

    res = []
    schema = table_schema(name, session)
    for column in schema.columns:
        res.append(column.name)
    return res


def table_add_column(table_name, name, type, session, default=None):
    """Adds a column to a table"""
    if name in table_columns(table_name, session):
        # If the column already exists, we don't have to do anything.
        return
    statement = 'ALTER TABLE %s ADD %s %s' % (table_name, name, type)
    if default:
        statement += ' DEFAULT %s' % default
    session.execute(statement)


def drop_tables(names, session):
    """Takes a list of table names and drops them from the database if they exist."""
    metadata = MetaData(bind=session.bind, reflect=True)
    for table in metadata.sorted_tables:
        if table.name in names:
            table.drop()
