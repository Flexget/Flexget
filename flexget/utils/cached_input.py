from __future__ import unicode_literals, division, absolute_import

import copy
import logging
import pickle
from datetime import datetime, timedelta

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from flexget import db_schema
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.utils import json
from flexget.utils.database import entry_synonym
from flexget.utils.sqlalchemy_utils import table_schema, table_add_column
from flexget.utils.tools import parse_timedelta, TimedDict, get_config_hash
from sqlalchemy import Column, Integer, String, DateTime, Unicode, select, ForeignKey
from sqlalchemy.orm import relation

log = logging.getLogger('input_cache')
Base = db_schema.versioned_base('input_cache', 1)


@db_schema.upgrade('input_cache')
def upgrade(ver, session):
    if ver == 0:
        table = table_schema('input_cache_entry', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('input_cache_entry', session)
        for row in session.execute(select([table.c.id, table.c.entry])):
            try:
                p = pickle.loads(row['entry'])
                session.execute(table.update().where(table.c.id == row['id']).values(
                    json=json.dumps(p, encode_datetime=True)))
            except KeyError as e:
                log.error('Unable error upgrading input_cache pickle object due to %s' % str(e))
        ver = 1
    return ver


class InputCache(Base):
    __tablename__ = 'input_cache'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    hash = Column(String)
    added = Column(DateTime, default=datetime.now)

    entries = relation('InputCacheEntry', backref='cache', cascade='all, delete, delete-orphan')


class InputCacheEntry(Base):
    __tablename__ = 'input_cache_entry'

    id = Column(Integer, primary_key=True)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')

    cache_id = Column(Integer, ForeignKey('input_cache.id'), nullable=False)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    """Removes old input caches from plugins that are no longer configured."""
    result = session.query(InputCache).filter(InputCache.added < datetime.now() - timedelta(days=7)).delete()
    if result:
        log.verbose('Removed %s old input caches.' % result)


class cached(object):
    """
    Implements transparent caching decorator @cached for inputs.

    Decorator has two parameters:

    * **name** in which the configuration is present in tasks configuration.
    * **key** in which the configuration has the cached resource identifier (ie. url).
      If the key is not given or present in the configuration :name: is expected to be a cache name (ie. url)

    .. note:: Configuration assumptions may make this unusable in some (future) inputs
    """

    cache = TimedDict(cache_time='5 minutes')

    def __init__(self, name, persist=None):
        # Cast name to unicode to prevent sqlalchemy warnings when filtering
        self.name = str(name)
        # Parse persist time
        self.persist = persist and parse_timedelta(persist)

    def __call__(self, func):

        def wrapped_func(*args, **kwargs):
            # get task from method parameters
            task = args[1]

            # detect api version
            api_ver = 1
            if len(args) == 3:
                api_ver = 2

            if api_ver == 1:
                # get name for a cache from tasks configuration
                if self.name not in task.config:
                    raise Exception('@cache config name %s is not configured in task %s' % (self.name, task.name))
                hash = get_config_hash(task.config[self.name])
            else:
                hash = get_config_hash(args[2])

            log.trace('self.name: %s' % self.name)
            log.trace('hash: %s' % hash)

            cache_name = self.name + '_' + hash
            log.debug('cache name: %s (has: %s)' % (cache_name, ', '.join(list(self.cache.keys()))))

            cache_value = self.cache.get(cache_name, None)

            if not task.options.nocache and cache_value:
                # return from the cache
                log.trace('cache hit')
                entries = []
                for entry in cache_value:
                    fresh = copy.deepcopy(entry)
                    entries.append(fresh)
                if entries:
                    log.verbose('Restored %s entries from cache' % len(entries))
                return entries
            else:
                if self.persist and not task.options.nocache:
                    # Check database cache
                    with Session() as session:
                        db_cache = session.query(InputCache).filter(InputCache.name == self.name). \
                            filter(InputCache.hash == hash). \
                            filter(InputCache.added > datetime.now() - self.persist). \
                            first()
                        if db_cache:
                            entries = [e.entry for e in db_cache.entries]
                            log.verbose('Restored %s entries from db cache' % len(entries))
                            # Store to in memory cache
                            self.cache[cache_name] = copy.deepcopy(entries)
                            return entries

                # Nothing was restored from db or memory cache, run the function
                log.trace('cache miss')
                # call input event
                try:
                    response = func(*args, **kwargs)
                except PluginError as e:
                    # If there was an error producing entries, but we have valid entries in the db cache, return those.
                    if self.persist and not task.options.nocache:
                        with Session() as session:
                            db_cache = session.query(InputCache).filter(InputCache.name == self.name). \
                                filter(InputCache.hash == hash).first()
                            if db_cache and db_cache.entries:
                                log.error('There was an error during %s input (%s), using cache instead.' %
                                          (self.name, e))
                                entries = [ent.entry for ent in db_cache.entries]
                                log.verbose('Restored %s entries from db cache' % len(entries))
                                # Store to in memory cache
                                self.cache[cache_name] = copy.deepcopy(entries)
                                return entries
                    # If there was nothing in the db cache, re-raise the error.
                    raise
                if api_ver == 1:
                    response = task.entries
                if not isinstance(response, list):
                    log.warning('Input %s did not return a list, cannot cache.' % self.name)
                    return response
                # store results to cache
                log.debug('storing to cache %s %s entries' % (cache_name, len(response)))
                try:
                    self.cache[cache_name] = copy.deepcopy(response)
                except TypeError:
                    # might be caused because of backlog restoring some idiotic stuff, so not neccessarily a bug
                    log.critical('Unable to save task content into cache, '
                                 'if problem persists longer than a day please report this as a bug')
                if self.persist:
                    # Store to database
                    log.debug('Storing cache %s to database.' % cache_name)
                    with Session() as session:
                        db_cache = session.query(InputCache).filter(InputCache.name == self.name). \
                            filter(InputCache.hash == hash).first()
                        if not db_cache:
                            db_cache = InputCache(name=self.name, hash=hash)
                        db_cache.entries = [InputCacheEntry(entry=ent) for ent in response]
                        db_cache.added = datetime.now()
                        session.merge(db_cache)
                return response

        return wrapped_func
