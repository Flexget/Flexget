from sqlalchemy.schema import Table, MetaData
from sqlalchemy.exceptions import NoSuchTableError


def table_exists(name, session):
    """Hack, return True if table_name exists """

    try:
        meta = MetaData(bind=session.connection())
        Table(name, meta, autoload=True, autoload_with=session.connection())
    except NoSuchTableError:
        return False
    return True


def table_schema(name, session):
    """Hack, return table schema"""

    try:
        meta = MetaData(bind=session.connection())
        reflect = Table(name, meta, autoload=True, autoload_with=session.connection())
        return reflect
    except NoSuchTableError:
        return None


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


def drop_tables(names, session):
    """Takes a list of table names and drops them from the database if they exist."""
    metadata = MetaData(bind=session.bind, reflect=True)
    for table in metadata.sorted_tables:
        if table.name in names:
            table.drop()
