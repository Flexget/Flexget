import copy
import pickle
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional

from loguru import logger
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Unicode, select
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import relation

from flexget import db_schema
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.utils import json, serialization
from flexget.utils.database import entry_synonym
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema
from flexget.utils.tools import TimedDict, get_config_hash, parse_timedelta

logger = logger.bind(name='input_cache')

if TYPE_CHECKING:

    class Base:
        def __init__(self, *args, **kwargs) -> None:
            ...

else:
    Base = db_schema.versioned_base('input_cache', 2)


@db_schema.upgrade('input_cache')
def upgrade(ver: int, session: DBSession) -> int:
    if ver == 0:
        table = table_schema('input_cache_entry', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('input_cache_entry', session)
        for row in session.execute(select([table.c.id, table.c.entry])):
            try:
                p = pickle.loads(row['entry'])
                session.execute(
                    table.update()
                    .where(table.c.id == row['id'])
                    .values(json=json.dumps(p, encode_datetime=True))
                )
            except KeyError as ex:
                logger.error(f'Unable error upgrading input_cache pickle object due to {ex}')
        ver = 1
    if ver == 1:
        table = table_schema('input_cache_entry', session)
        for row in session.execute(select([table.c.id, table.c.json])):
            if not row['json']:
                # Seems there could be invalid data somehow. See #2590
                continue
            data = json.loads(row['json'], decode_datetime=True)
            # If title looked like a date, make sure it's a string
            # Had a weird case of an entry without a title: https://github.com/Flexget/Flexget/issues/2636
            title = data.pop('title', None)
            entry = partial(Entry, **data)
            e = entry(title=str(title)) if title else entry()
            session.execute(
                table.update().where(table.c.id == row['id']).values(json=serialization.dumps(e))
            )

        ver = 2
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
def db_cleanup(manager, session: DBSession) -> None:
    """Removes old input caches from plugins that are no longer configured."""
    result = (
        session.query(InputCache)
        .filter(InputCache.added < datetime.now() - timedelta(days=7))
        .delete()
    )
    if result:
        logger.verbose('Removed {} old input caches.', result)


class cached:
    """
    Implements transparent caching decorator @cached for inputs.

    Decorator has two parameters:

    * **name** in which the configuration is present in tasks configuration.
    * **key** in which the configuration has the cached resource identifier (ie. url).
      If the key is not given or present in the configuration :name: is expected to be a cache name (ie. url)

    .. note:: Configuration assumptions may make this unusable in some (future) inputs
    """

    cache = TimedDict(cache_time='5 minutes')

    def __init__(self, name: str, persist: str = None) -> None:
        # Cast name to unicode to prevent sqlalchemy warnings when filtering
        self.name = str(name)
        # Parse persist time
        self.persist: Optional[timedelta] = parse_timedelta(persist) if persist else None
        # Will be set when wrapped function is called
        self.config_hash = None
        self.cache_name = None

    def __call__(self, func):
        def wrapped_func(*args, **kwargs):
            # get task from method parameters
            task = args[1]
            self.config_hash = get_config_hash(args[2])

            logger.trace('self.name: {}', self.name)
            logger.trace('hash: {}', self.config_hash)

            self.cache_name = self.name + '_' + self.config_hash
            logger.debug(
                'cache name: {} (has: {})', self.cache_name, ', '.join(list(self.cache.keys()))
            )

            if not task.options.nocache:
                cache_value = self.cache.get(self.cache_name, None)
                if cache_value:
                    # return from the cache
                    logger.verbose('Restored entries from cache')
                    return cache_value

                if self.persist:
                    # Check database cache
                    db_cache = self.load_from_db()
                    if db_cache is not None:
                        return db_cache

            # Nothing was restored from db or memory cache, run the function
            logger.trace('cache miss')
            # call input event
            try:
                response = func(*args, **kwargs)
            except PluginError as e:
                # If there was an error producing entries, but we have valid entries in the db cache, return those.
                if self.persist and not task.options.nocache:
                    cache = self.load_from_db(load_expired=True)
                    if cache is not None:
                        logger.error(
                            'There was an error during {} input ({}), using cache instead.',
                            self.name,
                            e,
                        )
                        return cache
                # If there was nothing in the db cache, re-raise the error.
                raise
            # store results to cache
            logger.debug('storing entries to cache {} ', self.cache_name)
            cache = IterableCache(response, self.store_to_db if self.persist else None)
            self.cache[self.cache_name] = cache
            return cache

        return wrapped_func

    def store_to_db(self, entries: List[str]):
        # Store to database
        logger.debug(f'Storing cache {self.cache_name} to database.')
        with Session() as session:
            db_cache = (
                session.query(InputCache)
                .filter(InputCache.name == self.name)
                .filter(InputCache.hash == self.config_hash)
                .first()
            )
            if not db_cache:
                db_cache = InputCache(name=self.name, hash=self.config_hash)
            db_cache.entries = [InputCacheEntry(entry=ent) for ent in entries]
            db_cache.added = datetime.now()
            session.merge(db_cache)

    def load_from_db(self, load_expired: bool = False) -> Optional[List[InputCacheEntry]]:
        with Session() as session:
            db_cache = (
                session.query(InputCache)
                .filter(InputCache.name == self.name)
                .filter(InputCache.hash == self.config_hash)
            )
            if self.persist and not load_expired:
                db_cache = db_cache.filter(InputCache.added > datetime.now() - self.persist)
            db_cache = db_cache.first()
            if db_cache:
                entries = [ent.entry for ent in db_cache.entries]
                logger.verbose(f'Restored {len(entries)} entries from db cache')
                # Store to in memory cache
                self.cache[self.cache_name] = copy.deepcopy(entries)
                return entries
            return None


class IterableCache:
    """
    Can cache any iterable (including generators) without immediately evaluating all entries.
    If `finished_hook` is supplied, it will be called the first time the iterable is run to the end.
    """

    def __init__(self, iterable: Iterable, finished_hook: Callable[[List], None] = None):
        self.iterable = iter(iterable)
        self.cache: List = []
        self.finished_hook = finished_hook

    def __iter__(self):
        for item in self.cache:
            yield copy.deepcopy(item)
        for item in self.iterable:
            self.cache.append(item)
            yield copy.deepcopy(item)
        # The first time we iterate through all items, call our finished hook with complete list of items
        if self.finished_hook:
            self.finished_hook(self.cache)
            self.finished_hook = None
