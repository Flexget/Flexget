from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime
from sqlalchemy import Column, String, Unicode, DateTime, Integer
import logging

from flexget import db_schema, plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.database import quality_property
from flexget.db_schema import Session
from flexget.utils import qualities
from flexget.utils.tools import parse_timedelta, group_entries

log = logging.getLogger('timeframe')

Base = db_schema.versioned_base('upgrade', 0)

entry_actions = {
    'accept': Entry.accept,
    'reject': Entry.reject,
}


class EntryTimeFrame(Base):
    __tablename__ = 'timeframe'

    id = Column(Unicode, primary_key=True, index=True)
    status = Column(Unicode)
    title = Column(Unicode)
    _quality = Column('quality', String)
    quality = quality_property('_quality')
    first_seen = Column(DateTime, default=datetime.now())
    proper_count = Column(Integer, default=0)

    def __str__(self):
        return '<Timeframe(id=%s,added=%s,quality=%s)>' % \
               (self.id, self.added, self.quality)


class FilterTimeFrame(object):
    schema = {
        'type': 'object',
        'properties': {
            'identified_by': {'type': 'string', 'default': 'auto'},
            'target': {'type': 'string', 'format': 'quality_requirements'},
            'wait': {'type': 'string', 'format': 'interval'},
            'on_waiting': {'type': 'string', 'enum': ['accept', 'reject', 'do_nothing'], 'default': 'reject'},
            'on_reached': {'type': 'string', 'enum': ['accept', 'reject', 'do_nothing'], 'default': 'do_nothing'},
        },
        'required': ['target', 'wait'],
        'additionalProperties': False
    }

    def __init__(self):
        try:
            self.backlog = plugin.get_plugin_by_name('backlog')
        except plugin.DependencyError:
            self.backlog = None
            log.warning('Unable to utilize backlog plugin, so episodes may slip through timeframe.')

    # Run last so we work on only accepted entries
    @plugin.priority(-255)
    def on_task_filter(self, task, config):
        if not config:
            return

        identified_by = '{{ id }}' if config['identified_by'] == 'auto' else config['identified_by']

        grouped_entries = group_entries(task.accepted, identified_by)
        if not grouped_entries:
            return

        action_on_waiting = entry_actions[config['on_waiting']] if config['on_waiting'] != 'do_nothing' else None
        action_on_reached = entry_actions[config['on_reached']] if config['on_reached'] != 'do_nothing' else None

        with Session() as session:
            # Prefetch Data
            existing_ids = session.query(EntryTimeFrame).filter(EntryTimeFrame.id.in_(grouped_entries.keys())).all()
            existing_ids = {e.id: e for e in existing_ids}

            for identifier, entries in grouped_entries.items():
                if not entries:
                    continue

                id_timeframe = existing_ids.get(identifier)
                if not id_timeframe:
                    id_timeframe = EntryTimeFrame()
                    id_timeframe.id = identifier
                    id_timeframe.status = 'waiting'
                    id_timeframe.first_seen = datetime.now()
                    session.add(id_timeframe)

                if id_timeframe.status == 'accepted':
                    log.debug('Previously accepted %s with %s skipping', identifier, id_timeframe.title)
                    continue

                # Sort entities in order of quality and best proper
                entries.sort(key=lambda e: (e['quality'], e.get('proper_count', 0)), reverse=True)
                best_entry = entries[0]

                log.debug('Current best for identifier %s is %s', identifier, best_entry['title'])

                id_timeframe.title = best_entry['title']
                id_timeframe.quality = best_entry['quality']
                id_timeframe.proper_count = best_entry.get('proper_count', 0)

                # Check we hit target or better
                target_requirement = qualities.Requirements(config['target'])
                target_quality = qualities.Quality(config['target'])
                if target_requirement.allows(best_entry['quality']) or best_entry['quality'] >= target_quality:
                    log.debug('timeframe reach target quality %s or higher for %s' % (target_quality, identifier))
                    if action_on_reached:
                        action_on_reached(best_entry, 'timeframe reached target quality or higher')
                    continue

                # Check if passed wait time
                expires = id_timeframe.first_seen + parse_timedelta(config['wait'])
                if expires <= datetime.now():
                    log.debug('timeframe expired, releasing quality restriction for %s' % identifier)
                    if action_on_reached:
                        action_on_reached(best_entry, 'timeframe wait expired')
                    continue

                # Verbose waiting, add to backlog
                if action_on_waiting:
                    for entry in entries:
                        action_on_waiting(entry, 'timeframe waiting')
                diff = expires - datetime.now()
                hours, remainder = divmod(diff.seconds, 3600)
                hours += diff.days * 24
                minutes, _ = divmod(remainder, 60)

                log.info('`%s`: timeframe waiting for %02dh:%02dmin. Currently best is `%s`.', identifier, hours,
                         minutes, best_entry['title'])

                # add best entry to backlog (backlog is able to handle duplicate adds)
                if self.backlog:
                    self.backlog.instance.add_backlog(task, best_entry, session=session)

    def on_task_learn(self, task, config):
        if not config:
            return

        identified_by = '{{ id }}' if config['identified_by'] == 'auto' else config['identified_by']

        grouped_entries = group_entries(task.accepted, identified_by)
        if not grouped_entries:
            return

        with Session() as session:
            # Prefetch Data
            existing_ids = session.query(EntryTimeFrame).filter(EntryTimeFrame.id.in_(grouped_entries.keys())).all()
            existing_ids = {e.id: e for e in existing_ids}

            for identifier, entries in grouped_entries.items():
                if not entries:
                    continue

                id_timeframe = existing_ids.get(identifier)

                if not id_timeframe:
                    continue

                # Sort entities in order of quality
                entries.sort(key=lambda e: e['quality'], reverse=True)

                # First entry will be the best quality
                best_entry = entries[0]

                id_timeframe.quality = best_entry['quality']
                id_timeframe.title = best_entry['title']
                id_timeframe.proper_count = best_entry.get('proper_count', 0)
                id_timeframe.status = 'accepted'


@event('plugin.register')
def register_plugin():
    plugin.register(FilterTimeFrame, 'timeframe', api_ver=2)
