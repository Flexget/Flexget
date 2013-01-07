from __future__ import unicode_literals, division, absolute_import
import logging

from sqlalchemy import Column, Integer, String

from flexget.manager import Base, Session
from flexget.event import event
from flexget.utils.database import with_session
from flexget.utils.sqlalchemy_utils import table_schema

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
    base_version = plugin_schemas[plugin]['version']
    if version != base_version:
        raise ValueError('Tried to set %s plugin schema version to %d when '
                         'it should be %d as defined in versioned_base.' % (plugin, version, base_version))
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

    The wrapped function will be passed the current schema version and a session object.
    The function should return the new version of the schema after the upgrade.

    There is no need to commit the session, it will commit automatically if an upgraded
    schema version is returned.

    Example::

      from flexget import schema
      @schema.upgrade('your_plugin')
      def upgrade(ver, session):
           if ver == 2:
               # upgrade
               ver = 3
           return ver
    """

    def upgrade_decorator(func):

        @event('manager.upgrade')
        def upgrade_wrapper(manager):
            ver = get_version(plugin)
            session = Session()
            try:
                new_ver = func(ver, session)
                if new_ver > ver:
                    log.info('Plugin `%s` schema upgraded successfully' % plugin)
                    set_version(plugin, new_ver)
                    session.commit()
                    manager.db_upgraded = True
                elif new_ver < ver:
                    log.critical('A lower schema version was returned (%s) from the %s upgrade function '
                                 'than passed in (%s)' % (new_ver, plugin, ver))
                    manager.disable_tasks()
            except Exception as e:
                log.exception('Failed to upgrade database for plugin %s: %s' % (plugin, e))
                manager.disable_tasks()
            finally:
                session.close()

        return upgrade_wrapper
    return upgrade_decorator


@with_session
def reset_schema(plugin, session=None):
    """
    Removes all tables from given plugin from the database, as well as removing current stored schema number.

    :param plugin: The plugin whose schema should be reset
    """
    if plugin not in plugin_schemas:
        raise ValueError('The plugin %s has no stored schema to reset.' % plugin)
    table_names = plugin_schemas[plugin].get('tables', [])
    tables = [table_schema(name, session) for name in table_names]
    # Remove the plugin's tables
    for table in tables:
        table.drop()
    # Remove the plugin from schema table
    session.query(PluginSchema).filter(PluginSchema.plugin == plugin).delete()
    # Create new empty tables
    Base.metadata.create_all(bind=session.bind)
    session.commit()


def register_plugin_table(tablename, plugin, version):
    plugin_schemas.setdefault(plugin, {'version': version, 'tables': []})
    if plugin_schemas[plugin]['version'] != version:
        raise Exception('Two different schema versions received for plugin %s' % plugin)
    plugin_schemas[plugin]['tables'].append(tablename)


class Meta(type):
    """Metaclass for objects returned by versioned_base factory"""

    def __new__(mcs, metaname, bases, dict_):
        """This gets called when a class that subclasses VersionedBase is defined."""
        new_bases = []
        for base in bases:
            # Check if we are creating a subclass of VersionedBase
            if base.__name__ == 'VersionedBase':
                # Register this table in plugin_schemas
                register_plugin_table(dict_['__tablename__'], base.plugin, base.version)
                # Make sure the resulting class also inherits from Base
                if not any(isinstance(base, type(Base)) for base in bases):
                    # We are not already subclassing Base, add it in to the list of bases instead of VersionedBase
                    new_bases.append(Base)
                    # Since Base and VersionedBase have 2 different metaclasses, a class that subclasses both of them
                    # must have a metaclass that subclasses both of their metaclasses.

                    class mcs(type(Base), mcs):
                        pass
            else:
                new_bases.append(base)

        return type.__new__(mcs, str(metaname), tuple(new_bases), dict_)

    def __getattr__(self, item):
        """Transparently return attributes of Base instead of our own."""
        return getattr(Base, item)


def versioned_base(plugin, version):
    """Returns a class which can be used like Base, but automatically stores schema version when tables are created."""

    return Meta('VersionedBase', (object,), {'__metaclass__': Meta, 'plugin': plugin, 'version': version})


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
