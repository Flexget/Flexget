from flexget.manager import Base, Session
from sqlalchemy import Column, Integer, String
from sqlalchemy.schema import ForeignKey
import logging

log = logging.getLogger('schema')


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
            return 0
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
                schema.version(version)
        session.commit()
    finally:
        session.close()
