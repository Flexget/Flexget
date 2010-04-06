def table_exists(name, session):
    """Hack, return True if table_name exists """

    from sqlalchemy.exceptions import NoSuchTableError
    from sqlalchemy import Table, MetaData
    try:
        meta = MetaData(bind=session.connection())
        Table(name, meta, autoload=True, autoload_with=session.connection())
    except NoSuchTableError:
        return False
    return True


def table_schema(name, session):
    """Hack, return table schema"""

    from sqlalchemy.exceptions import NoSuchTableError
    from sqlalchemy import Table, MetaData
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
