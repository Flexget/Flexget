from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime

from abc import abstractmethod, abstractproperty
from abc import ABCMeta
from flexget.utils.log import log_once
from sqlalchemy import (Column, Integer, String, Unicode, DateTime, desc, ForeignKey)
from sqlalchemy.orm import relation
from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound


log = logging.getLogger('charts')

# region ChartsConnector
charts_connectors = {}
""" :type charts_connectors : dict of [ChartsConnector] """


# We need to wait until manager startup to access other plugin instances, to make sure they have all been loaded
@event('manager.startup')
def init_charts_connectors(manager):
    """Prepare our list of parsing plugins and default parsers."""
    for p in plugin.get_plugins(group='charts_connector'):
        organization = p.instance.organization
        charts_connectors[organization] = p.instance
        log.debug("New charts connector registered for %s" % organization)


class ChartsConnector(ABCMeta(str('ChartsConnectorABCMeta'), (object,), {})):
    @abstractproperty
    def organization(self):
        raise NotImplementedError()

    @abstractmethod
    def retrieve_charts(self, charts_type='radio', date_interval='week', **kargs):
        raise NotImplementedError()
# endregion

# region ORM definitions
SCHEMA_VER = 0
Base = db_schema.versioned_base('charts', SCHEMA_VER)


@db_schema.upgrade('charts_snep')
def upgrade(ver, session):
    return 0


class ChartsProvider(Base):
    __tablename__ = 'charts_provider'
    id = Column(Integer, primary_key=True)
    organization = Column(String, nullable=False) # Company, association, person etc who provides charts
    category = Column(String) # radio, album, streaming, all etc
    periodicity = Column(String)
    plugin_name = Column(String)
    releases = relation('ChartsRelease',
                        backref='provider',
                        cascade='all, delete, delete-orphan')


class ChartsRelease(Base):
    __tablename__ = 'charts_release'
    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey('charts_provider.id'), nullable=False)
    expires = Column(DateTime, nullable=False)
    entries = relation('ChartsEntry',
                       backref='release',
                       cascade='all, delete, delete-orphan')


class ChartsEntry(Base):
    __tablename__ = 'charts_entry'
    id = Column(Integer, primary_key=True)
    release_id = Column(Integer, ForeignKey('charts_release.id'), nullable=False)

    # TODO: Is enough generic?
    rank = Column(Integer)
    best_rank = Column(Integer)
    charted_weeks = Column(Integer)
    artist = Column(Unicode)
    title = Column(Unicode)
# endregion


class ChartsPlugin(object):
    """
    Example:
    charts:
      provider : snep
      category : radio
      max_best_rank : 5
      min_charted_weeks : 4
    """
    schema = {
        'type': 'object',
        'properties': {
            'provider': {'type': 'string'},
            'category': {'type': 'string'},
            'max_rank': {'type': 'integer'},
            'max_best_rank': {'type': 'integer'},
            'min_charted_weeks': {'type': 'integer'}
        },
        'additionalProperties': False,
        'required': ['provider', 'category']
    }

    def get_last_release_online(self, organization, category=None, periodicity=None):
        """
        Retrieves online the last charts release for a given provider.
        :rtype ChartsRelease
        """
        connector = charts_connectors.get(organization)
        if connector is None:
            log.warn("Charts connector for '%s' not found!" % organization)
            return None

        return connector.retrieve_charts(charts_type=category, date_interval=periodicity)

    def get_provider_id(self, organization, category=None, periodicity=None, auto_create=False):
        """
        Return the provider id for the given filters. If auto_create is set to True
        and the provider doesn't exist in DB then this method will create one and
         return its id.
        :type organization: str
        :type category: str
        :type periodicity: str
        :type auto_create: bool
        :rtype: int
        """

        session = Session()
        # region Retrieve a provider
        query = session.query(ChartsProvider.id).filter(ChartsProvider.organization == organization)
        if category:
            query = query.filter(ChartsProvider.category == category)
        if periodicity:
            query = query.filter(ChartsProvider.periodicity == periodicity)

        provider_part = None
        """:type KeyedTuple"""
        try:
            provider_part = query.one()
        except MultipleResultsFound:
            log.warn('Multiple charts provider was found. Please to accurate your filters.')
            provider_part = query.first()
        except NoResultFound:
            log.debug("None charts provider match given filters.")
            if auto_create:
                log.debug('No provider for %s:%s(%s). Creating one...' % (organization, category, periodicity))
                provider = ChartsProvider(
                    organization=organization,
                    category=category,
                    periodicity=periodicity
                )
                session.add(provider)
                session.commit()
                log.debug('Provider for %s:%s(%s) created (id=%d).' % (
                    organization, category, periodicity, provider.id))
                return provider.id
            return None
        finally:
            session.close()
        return provider_part.id

    def get_last_release_offline(self, provider_id):
        """
        Retrieves the charts latest charts release for a given provider.
        :type provider_id: int
        :rtype: ChartsRelease
        :return The latest ChartsRelease for the given information (expires or not). None if none release found.
        """
        session = Session()
        try:
            last_release = session.query(ChartsRelease, ChartsRelease.id, ChartsRelease.expires) \
                .filter(ChartsRelease.provider_id == provider_id) \
                .order_by(desc("expires")).first()
            return last_release
        except NoResultFound:
            log.debug("No release found for this provider (this case shouldn't appear!)")
            return None
        finally:
            session.close()

    def get_last_release(self, session, organization, category=None, periodicity=None):
        # region Attempting offline retrieving
        online_reason = None
        provider_id = self.get_provider_id(organization, category, periodicity, auto_create=True)
        last_release = self.get_last_release_offline(provider_id)

        if last_release is None:
            online_reason = 'no cached release found.'
        elif last_release.expires < datetime.now():
            online_reason = 'latest cached charts release expired.'
        # endregion

        if online_reason:
            log.debug("Attempting to retrieve charts online because %s" % online_reason)
            last_release = self.get_last_release_online(organization, category, periodicity)
            last_release.provider_id = provider_id
            session.add(last_release)
            session.commit()

        return last_release

    def on_task_filter(self, task, config):
        session = Session()

        charts_release = self.get_last_release(session, config.get("provider"),
                                               config.get("category"), config.get("periodicity"))
        lookup = plugin.get_plugin_by_name('music').instance.guess_entry

        for entry in task.entries:
            lookup(entry)

            if not entry.get('music_title'):
                continue
            charts_entry = session\
                .query(ChartsEntry, ChartsEntry.artist, ChartsEntry.title, ChartsEntry.rank, ChartsEntry.best_rank, ChartsEntry.charted_weeks)\
                .filter(
                    ChartsEntry.release_id == charts_release.id,
                    ChartsEntry.artist.ilike(entry.get('music_artist')),
                    ChartsEntry.title.ilike(entry.get('music_title')))\
                .first()
            """:type charts_entry: ChartsEntry"""

            reasons = []
            if not charts_entry:
                reasons.append("uncharted")
            else:
                if config.get('max_rank') and charts_entry.rank > config.get('max_rank'):
                    reasons.append("max_rank (%s > %s)" % (charts_entry.rank, config.get('max_rank')))
                if config.get('max_best_rank') and charts_entry.best_rank > config.get('max_best_rank'):
                    reasons.append("max_best_rank (%s > %s)" % (charts_entry.best_rank, config.get('max_best_rank')))
                if config.get('min_charted_weeks') and charts_entry.charted_weeks < config.get('min_charted_weeks'):
                    reasons.append("min_charted_weeks (%s < %s)"
                                   % (charts_entry.charted_weeks, config.get('min_charted_weeks')))

            if reasons:
                msg = 'Didn\'t accept `%s` because of rule(s) %s' % \
                      (entry.get('music_title', None) or entry['title'], ', '.join(reasons))
                if task.options.debug:
                    log.debug(msg)
                else:
                    if task.options.cron:
                        log_once(msg, log)
                    else:
                        log.info(msg)
            else:
                entry.accept()


@event('plugin.register')
def register_plugin():
    plugin.register(ChartsPlugin, 'charts', api_ver=2)