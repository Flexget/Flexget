import logging
from sqlalchemy import Column, Integer, String
from flexget.manager import Base, Session
from flexget.event import event

log = logging.getLogger('schema')

# Stores a mapping of {plugin: {'version': version, 'tables': ['table_names'])}
plugin_schemas = {}


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
            log.debug('No schema version stored for %s' % plugin)
            return None
        else:
            return schema.version
    finally:
        session.close()


def set_version(plugin, version):
    if plugin not in plugin_schemas:
        raise ValueError('Tried to set schema version for %s plugin with no versioned_base.' % plugin)
    if version != plugin_schemas[plugin]['version']:
        raise ValueError('Tried to set %s plugin schema version not equal to that defined in versioned_base.' % plugin)
    session = Session()
    try:
        schema = session.query(PluginSchema).filter(PluginSchema.plugin == plugin).first()
        if not schema:
            log.debug('Initializing plugin %s schema version to %i' % (plugin, version))
            schema = PluginSchema(plugin, version)
            session.add(schema)
        else:
            if version < schema.version:
                raise ValueError('Tried to set plugin %s schema version to lower value' % plugin)
            if version != schema.version:
                log.debug('Updating plugin %s schema version to %i' % (plugin, version))
                schema.version = version
        session.commit()
    finally:
        session.close()


def upgrade(plugin):
    """Used as a decorator to register a schema upgrade function.

    The wrapped function will be passed the current schema version and a session object. The function should return the
    new version of the schema after the upgrade.

    There is no need to commit the session, it will commit automatically if an upgraded schema version is returned."""

    def upgrade(func):

        @event('manager.upgrade')
        def upgrade(manager):
            ver = get_version(plugin)
            session = Session()
            try:
                new_ver = func(ver, session)
                if new_ver > ver:
                    set_version(plugin, new_ver)
                    session.commit()
                elif new_ver < ver:
                    log.critical('A lower schema version was returned (%s) from the %s upgrade function '
                                 'than passed in (%s)' % (new_ver, plugin, ver))
                    manager.disable_feeds()
            except Exception, e:
                log.exception('Failed to upgrade database for plugin %s: %s' % (plugin, e))
                manager.disable_feeds()
            finally:
                session.close()

        return upgrade
    return upgrade


def versioned_base(plugin, version):
    """Returns a class which can be used like Base, but automatically stores schema version when tables are created."""

    class Meta(type):

        def __new__(mcs, metaname, bases, dict_):
            """This gets called when a class that subclasses VersionedBase is defined."""
            if '__tablename__' in dict_:
                # Record the table name to schema version mapping
                global plugin_schemas
                plugin_schemas.setdefault(plugin, {'version': version, 'tables': []})
                if plugin_schemas[plugin]['version'] != version:
                    raise Exception('Two different schema versions recieved for plugin %s' % plugin)
                plugin_schemas[plugin]['tables'].append(dict_['__tablename__'])
                # Make sure the resulting class also inherits from Base
                bases = bases + (Base,)

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


def after_table_create(event, target, bind, tables=None, **kw):
    """Sets the schema version to most recent for a plugin when it's tables are freshly created."""
    if tables:
        tables = [table.name for table in tables]
        for plugin, info in plugin_schemas.iteritems():
            # Only set the version if all tables for a given plugin are being created
            if all(table in tables for table in info['tables']):
                set_version(plugin, info['version'])

# Register a listener to call our method after tables are created
Base.metadata.append_ddl_listener('after-create', after_table_create)
