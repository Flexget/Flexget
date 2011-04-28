import logging
from flexget.manager import Base, Session
from sqlalchemy import Column, Integer, String

log = logging.getLogger('schema')

# Stores a mapping of {table_name: (schema_name, schema_version)}
table_schemas = {}


class PluginSchema(Base):

    __tablename__ = 'plugin_schema'

    id = Column(Integer, primary_key=True)
    plugin = Column(String)
    version = Column(Integer)

    def __init__(self, plugin, version=0):
        self.plugin = plugin
        self.version = version

    def __str__(self):
        return '<PluginSchema(plugin=%s,version=%i)>' % (self.plugin, self.version)


def get_version(plugin):
    session = Session()
    try:
        schema = session.query(PluginSchema).filter(PluginSchema.plugin == plugin).first()
        if not schema:
            log.debug('no schema version stored for %s' % plugin)
            return None
        else:
            return schema.version
    finally:
        session.close()


def set_version(plugin, version):
    session = Session()
    try:
        schema = session.query(PluginSchema).filter(PluginSchema.plugin == plugin).first()
        if not schema:
            log.debug('creating plugin %s schema version to %i' % (plugin, version))
            schema = PluginSchema(plugin, version)
            session.add(schema)
        else:
            if version < schema.version:
                raise ValueError('Tried to set plugin %s schema version to lower value' % plugin)
            if version != schema.version:
                log.debug('updating plugin %s schema version to %i' % (plugin, version))
                schema.version = version
        session.commit()
    finally:
        session.close()


def versioned_base(schema_name, schema_version):
    """Returns a class which can be used like Base, but automatically stores schema version when tables are created."""

    class Meta(type):

        def __new__(mcs, metaname, bases, dict_):
            """This gets called when a class that subclasses VersionedBase is defined."""
            if '__tablename__' in dict_:
                # Record the table name to schema version mapping
                global table_schemas
                table_schemas[dict_['__tablename__']] = (schema_name, schema_version)
                # Make sure the resulting class also inherits from Base
                bases = (Base,) + bases

                # Since Base and VersionedBase have 2 different metaclasses, a class that subclasses both of them
                # must have a metaclass that subclasses both of their metaclasses.

                class mcs(type(Base), mcs):
                    pass
            return type.__new__(mcs, metaname, bases, dict_)

        def __getattr__(self, item):
            """Transparently return attributes of Base instead of our own."""
            return getattr(Base, item)

    class VersionedBase(object):
        """Subclassing this class causes your table names to be registered into the schema registry,
        as well as causing your class to also subclass Base."""
        __metaclass__ = Meta

    return VersionedBase


def after_table_create(event, target, bind, tables=None):
    """Sets the schema version to most recent for a plugin when it's tables are freshly created."""
    if tables:
        for table in tables:
            if table.name in table_schemas:
                set_version(*table_schemas[table.name])

# Register a listener to be called after tables are created
Base.metadata.append_ddl_listener('after-create', after_table_create)
