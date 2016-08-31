from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import native_str

import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.exc import OperationalError

import flexget
from flexget.event import event
from flexget.manager import Base, Session
from flexget.utils.database import with_session
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import get_current_flexget_version

log = logging.getLogger('schema')

# Stores a mapping of {plugin: {'version': version, 'tables': ['table_names'])}
plugin_schemas = {}


class FlexgetVersion(Base):
    __tablename__ = 'flexget_version'

    version = Column(String, primary_key=True)
    created = Column(DateTime, default=datetime.now)

    def __init__(self):
        self.version = get_current_flexget_version()


@event('manager.startup')
def set_flexget_db_version(manager=None):
    with Session() as session:
        db_version = session.query(FlexgetVersion).first()
        if not db_version:
            log.debug('entering flexget version %s to db', get_current_flexget_version())
            session.add(FlexgetVersion())
        elif db_version.version != get_current_flexget_version():
            log.debug('updating flexget version %s in db', get_current_flexget_version())
            db_version.version = get_current_flexget_version()
            db_version.created = datetime.now()
            session.commit()
        else:
            log.debug('current flexget version already exist in db %s', db_version.version)


def get_flexget_db_version():
    with Session() as session:
        version = session.query(FlexgetVersion).first()
        if version:
            return version.version


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


@with_session
def get_version(plugin, session=None):
    schema = session.query(PluginSchema).filter(PluginSchema.plugin == plugin).first()
    if not schema:
        log.debug('No schema version stored for %s' % plugin)
        return None
    else:
        return schema.version


@with_session
def set_version(plugin, version, session=None):
    if plugin not in plugin_schemas:
        raise ValueError('Tried to set schema version for %s plugin with no versioned_base.' % plugin)
    base_version = plugin_schemas[plugin]['version']
    if version != base_version:
        raise ValueError('Tried to set %s plugin schema version to %d when '
                         'it should be %d as defined in versioned_base.' % (plugin, version, base_version))
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


@with_session
def upgrade_required(session=None):
    """Returns true if an upgrade of the database is required."""
    old_schemas = session.query(PluginSchema).all()
    if len(old_schemas) < len(plugin_schemas):
        return True
    for old_schema in old_schemas:
        if old_schema.plugin in plugin_schemas and old_schema.version < plugin_schemas[old_schema.plugin]['version']:
            return True
    return False


class UpgradeImpossible(Exception):
    """
    Exception to be thrown during a db upgrade function which will cause the old tables to be removed and recreated from
    the new model.
    """


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

    def upgrade_decorator(upgrade_func):

        @event('manager.upgrade')
        def upgrade_wrapper(manager):
            with Session() as session:
                current_ver = get_version(plugin, session=session)
                try:
                    new_ver = upgrade_func(current_ver, session)
                except UpgradeImpossible:
                    log.info('Plugin %s database is not upgradable. Flushing data and regenerating.' % plugin)
                    reset_schema(plugin, session=session)
                    manager.db_upgraded = True
                except Exception as e:
                    log.exception('Failed to upgrade database for plugin %s: %s' % (plugin, e))
                    session.rollback()
                    manager.shutdown(finish_queue=False)
                else:
                    current_ver = -1 if current_ver is None else current_ver
                    if new_ver > current_ver:
                        log.info('Plugin `%s` schema upgraded successfully' % plugin)
                        set_version(plugin, new_ver, session=session)
                        manager.db_upgraded = True
                    elif new_ver < current_ver:
                        log.critical('A lower schema version was returned (%s) from plugin %s upgrade function '
                                     'than passed in (%s)' % (new_ver, plugin, current_ver))
                        session.rollback()
                        manager.shutdown(finish_queue=False)

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
        try:
            table.drop()
        except OperationalError as e:
            if 'no such table' in str(e):
                continue
            raise e  # Remove the plugin from schema table
    session.query(PluginSchema).filter(PluginSchema.plugin == plugin).delete()
    # We need to commit our current changes to close the session before calling create_all
    session.commit()
    # Create new empty tables
    Base.metadata.create_all(bind=session.bind)


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

        return type.__new__(mcs, native_str(metaname), tuple(new_bases), dict_)

    def register_table(cls, table):
        """
        This can be used if a plugin is declaring non-declarative sqlalchemy tables.

        :param table: Can either be the name of the table, or an :class:`sqlalchemy.Table` instance.
        """
        if isinstance(table, str):
            register_plugin_table(table, cls.plugin, cls.version)
        else:
            register_plugin_table(table.name, cls.plugin, cls.version)

    def __getattr__(self, item):
        """Transparently return attributes of Base instead of our own."""
        return getattr(Base, item)


def versioned_base(plugin, version):
    """Returns a class which can be used like Base, but automatically stores schema version when tables are created."""

    return Meta('VersionedBase', (object,), {'__metaclass__': Meta, 'plugin': plugin, 'version': version})


def after_table_create(event, target, bind, tables=None, **kw):
    """Sets the schema version to most recent for a plugin when it's tables are freshly created."""
    if tables:
        # TODO: Detect if any database upgrading is needed and acquire the lock only in one place
        with flexget.manager.manager.acquire_lock(event=False):
            tables = [table.name for table in tables]
            for plugin, info in plugin_schemas.items():
                # Only set the version if all tables for a given plugin are being created
                if all(table in tables for table in info['tables']):
                    set_version(plugin, info['version'])


# Register a listener to call our method after tables are created
Base.metadata.append_ddl_listener('after-create', after_table_create)
