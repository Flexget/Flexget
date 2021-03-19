from datetime import datetime
from typing import Callable, Optional, Union, Dict, Any, List

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Table
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import DeclarativeMeta, as_declarative

import flexget
from flexget.event import event
from flexget.manager import Base, Session
from flexget.utils.database import with_session
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import get_current_flexget_version

logger = logger.bind(name='schema')

# Stores a mapping of {plugin: {'version': version, 'tables': ['table_names'])}
plugin_schemas: Dict[str, Dict[str, Any]] = {}


class FlexgetVersion(Base):
    __tablename__ = 'flexget_version'

    version = Column(String, primary_key=True)
    created = Column(DateTime, default=datetime.now)

    def __init__(self):
        self.version = get_current_flexget_version()


@event('manager.startup')
def set_flexget_db_version(manager=None) -> None:
    with Session() as session:
        db_version = session.query(FlexgetVersion).first()
        if not db_version:
            logger.debug('entering flexget version {} to db', get_current_flexget_version())
            session.add(FlexgetVersion())
        elif db_version.version != get_current_flexget_version():
            logger.debug('updating flexget version {} in db', get_current_flexget_version())
            db_version.version = get_current_flexget_version()
            db_version.created = datetime.now()
            session.commit()
        else:
            logger.debug('current flexget version already exist in db {}', db_version.version)


def get_flexget_db_version() -> Optional[str]:
    with Session() as session:
        version = session.query(FlexgetVersion).first()
        if version:
            return version.version
    return None


class PluginSchema(Base):
    __tablename__ = 'plugin_schema'

    id = Column(Integer, primary_key=True)
    plugin = Column(String)
    version = Column(Integer)

    def __init__(self, plugin: str, version: int = 0):
        self.plugin = plugin
        self.version = version

    def __str__(self) -> str:
        return f'<PluginSchema(plugin={self.plugin},version={self.version})>'


@with_session
def get_version(plugin: str, session=None) -> Optional[int]:
    schema = session.query(PluginSchema).filter(PluginSchema.plugin == plugin).first()
    if not schema:
        logger.debug('No schema version stored for {}', plugin)
        return None
    else:
        return schema.version


@with_session
def set_version(plugin: str, version: int, session=None) -> None:
    if plugin not in plugin_schemas:
        raise ValueError(
            f'Tried to set schema version for {plugin} plugin with no versioned_base.'
        )
    base_version = plugin_schemas[plugin]['version']
    if version != base_version:
        raise ValueError(
            f'Tried to set {plugin} plugin schema version to {version} when '
            f'it should be {base_version} as defined in versioned_base.'
        )
    schema = session.query(PluginSchema).filter(PluginSchema.plugin == plugin).first()
    if not schema:
        logger.debug('Initializing plugin {} schema version to {}', plugin, version)
        schema = PluginSchema(plugin, version)
        session.add(schema)
    else:
        if version < schema.version:
            raise ValueError(f'Tried to set plugin {plugin} schema version to lower value')
        if version != schema.version:
            logger.debug('Updating plugin {} schema version to {}', plugin, version)
            schema.version = version
    session.commit()


@with_session
def upgrade_required(session=None) -> bool:
    """Returns true if an upgrade of the database is required."""
    old_schemas = session.query(PluginSchema).all()
    if len(old_schemas) < len(plugin_schemas):
        return True
    for old_schema in old_schemas:
        if (
            old_schema.plugin in plugin_schemas
            and old_schema.version < plugin_schemas[old_schema.plugin]['version']
        ):
            return True
    return False


class UpgradeImpossible(Exception):
    """
    Exception to be thrown during a db upgrade function which will cause the old tables to be removed and recreated from
    the new model.
    """


def upgrade(plugin: str) -> Callable:
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
                    logger.info(
                        'Plugin {} database is not upgradable. Flushing data and regenerating.',
                        plugin,
                    )
                    reset_schema(plugin, session=session)
                    manager.db_upgraded = True
                except Exception as e:
                    logger.exception('Failed to upgrade database for plugin {}: {}', plugin, e)
                    session.rollback()
                    manager.shutdown(finish_queue=False)
                else:
                    current_ver = -1 if current_ver is None else current_ver
                    if new_ver > current_ver:
                        logger.info('Plugin `{}` schema upgraded successfully', plugin)
                        set_version(plugin, new_ver, session=session)
                        manager.db_upgraded = True
                    elif new_ver < current_ver:
                        logger.critical(
                            'A lower schema version was returned ({}) from plugin '
                            '{} upgrade function than passed in ({})',
                            new_ver,
                            plugin,
                            current_ver,
                        )
                        session.rollback()
                        manager.shutdown(finish_queue=False)

        return upgrade_wrapper

    return upgrade_decorator


@with_session
def reset_schema(plugin: str, session=None) -> None:
    """
    Removes all tables from given plugin from the database,
    as well as removing current stored schema number.

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


def register_plugin_table(tablename: str, plugin: str, version: int):
    plugin_schemas.setdefault(plugin, {'version': version, 'tables': []})
    if plugin_schemas[plugin]['version'] != version:
        raise Exception('Two different schema versions received for plugin %s' % plugin)
    plugin_schemas[plugin]['tables'].append(tablename)


class VersionedBaseMeta(DeclarativeMeta):
    """Metaclass for objects returned by versioned_base factory"""

    def __new__(mcs, metaname, bases, dict_):
        """This gets called when a class that subclasses VersionedBase is defined."""
        new_class = super().__new__(mcs, str(metaname), bases, dict_)
        if metaname != 'VersionedBase':
            register_plugin_table(new_class.__tablename__, new_class._plugin, new_class._version)
        return new_class

    def register_table(cls, table: Union[str, Table]) -> None:
        """
        This can be used if a plugin is declaring non-declarative sqlalchemy tables.

        :param table: Can either be the name of the table, or an :class:`sqlalchemy.Table` instance.
        """
        if isinstance(table, str):
            register_plugin_table(table, cls._plugin, cls._version)
        else:
            register_plugin_table(table.name, cls._plugin, cls._version)


def versioned_base(plugin: str, version: int) -> VersionedBaseMeta:
    """
    Returns a class which can be used like Base,
    but automatically stores schema version when tables are created.
    """

    @as_declarative(metaclass=VersionedBaseMeta, metadata=Base.metadata)
    class VersionedBase:
        _plugin = plugin
        _version = version

    return VersionedBase


def after_table_create(event, target, bind, tables: List[Table] = None, **kw) -> None:
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
