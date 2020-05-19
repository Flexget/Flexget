import pickle
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Index, Integer, String, Unicode, select

from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json, serialization
from flexget.utils.database import entry_synonym
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema
from flexget.utils.tools import parse_timedelta

logger = logger.bind(name='delay')
Base = db_schema.versioned_base('delay', 3)


class DelayedEntry(Base):
    __tablename__ = 'delay'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    title = Column(Unicode)
    expire = Column(DateTime)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')

    def __repr__(self):
        return '<DelayedEntry(title=%s)>' % self.title


Index('delay_feed_title', DelayedEntry.task, DelayedEntry.title)


# TODO: index "expire, task"


@db_schema.upgrade('delay')
def upgrade(ver, session):
    if ver is None:
        # Upgrade to version 0 was a failed attempt at cleaning bad entries from our table, better attempt in ver 1
        ver = 1
    if ver == 1:
        table = table_schema('delay', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('delay', session)
        failures = 0
        for row in session.execute(select([table.c.id, table.c.entry])):
            try:
                p = pickle.loads(row['entry'])
                session.execute(
                    table.update()
                    .where(table.c.id == row['id'])
                    .values(json=json.dumps(p, encode_datetime=True))
                )
            except (KeyError, ImportError):
                failures += 1
        if failures > 0:
            logger.error(
                'Error upgrading {} pickle objects. Some delay information has been lost.',
                failures,
            )
        ver = 2
    if ver == 2:
        table = table_schema('delay', session)
        for row in session.execute(select([table.c.id, table.c.json])):
            if not row['json']:
                # Seems there could be invalid data somehow. See #2590
                continue
            data = json.loads(row['json'], decode_datetime=True)
            # If title looked like a date, make sure it's a string
            title = str(data.pop('title'))
            e = Entry(title=title, **data)
            session.execute(
                table.update().where(table.c.id == row['id']).values(json=serialization.dumps(e))
            )
        ver = 3

    return ver


class FilterDelay:
    """
        Add delay to a task. This is useful for de-prioritizing expensive / bad-quality tasks.

        Format: n [minutes|hours|days|weeks]

        Example::

          delay: 2 hours
    """

    schema = {'type': 'string', 'format': 'interval'}

    def get_delay(self, config):
        logger.debug('delay: {}', config)
        try:
            return parse_timedelta(config)
        except ValueError:
            raise plugin.PluginError('Invalid time format', logger)

    @plugin.priority(-1)
    def on_task_input(self, task, config):
        """Captures the current input then replaces it with entries that have passed the delay."""
        if task.entries:
            logger.verbose('Delaying {} new entries for {}', len(task.entries), config)
            # Let details plugin know that it is ok if this task doesn't produce any entries
            task.no_entries_ok = True
        # First learn the current entries in the task to the database
        expire_time = datetime.now() + self.get_delay(config)
        for entry in task.entries:
            logger.debug('Delaying {}', entry['title'])
            # check if already in queue
            if (
                not task.session.query(DelayedEntry)
                .filter(DelayedEntry.title == entry['title'])
                .filter(DelayedEntry.task == task.name)
                .first()
            ):
                delay_entry = DelayedEntry()
                delay_entry.title = entry['title']
                delay_entry.entry = entry
                delay_entry.task = task.name
                delay_entry.expire = expire_time
                task.session.add(delay_entry)

        # Clear the current entries from the task now that they are stored
        task.all_entries[:] = []

        # Generate the list of entries whose delay has passed
        passed_delay = (
            task.session.query(DelayedEntry)
            .filter(datetime.now() > DelayedEntry.expire)
            .filter(DelayedEntry.task == task.name)
        )
        delayed_entries = [item.entry for item in passed_delay.all()]
        for entry in delayed_entries:
            entry['passed_delay'] = True
            logger.debug('Releasing {}', entry['title'])
        # Delete the entries from the db we are about to inject
        passed_delay.delete()

        if delayed_entries:
            logger.verbose('Restoring {} entries that have passed delay.', len(delayed_entries))
        # Return our delayed entries
        return delayed_entries


@event('plugin.register')
def register_plugin():
    plugin.register(FilterDelay, 'delay', api_ver=2)
