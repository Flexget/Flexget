def table_exists(table_name, feed):
    """ hack, return true if table_name exists """

    from sqlalchemy.exceptions import NoSuchTableError
    from sqlalchemy import Table, MetaData
    try:
        meta = MetaData()
        reflect = Table(table_name, meta, autoload=True, autoload_with=feed.session.connection())
    except NoSuchTableError:
        return True
    return False