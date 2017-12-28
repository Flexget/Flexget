from __future__ import unicode_literals, division, absolute_import
from builtins import *
from collections import defaultdict
from datetime import datetime
from sqlalchemy import Column, String, Unicode, DateTime, Integer
import logging

from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.utils.database import quality_property
from flexget.db_schema import Session
from flexget.event import event
from flexget.utils import qualities
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('upgrade')

Base = db_schema.versioned_base('upgrade', 0)

entry_actions = {
    'accept': Entry.accept,
    'reject': Entry.reject,
    'fail': Entry.fail
}


class EntryUpgrade(Base):
    __tablename__ = 'upgrade'

    id = Column(Unicode, primary_key=True, index=True)
    title = Column(Unicode)
    _quality = Column('quality', String)
    quality = quality_property('_quality')
    proper_count = Column(Integer, default=0)
    first_seen = Column(DateTime, default=datetime.now)
    updated = Column(DateTime, index=True, default=datetime.now)

    def __init__(self):
        self.first_seen = datetime.now()
        self.updated = datetime.now()

    def __str__(self):
        return '<Upgrade(id=%s,added=%s,quality=%s)>' % \
               (self.id, self.added, self.quality)


def group_entries(entries, identified_by):
    grouped_entries = defaultdict(list)

    # Group by Identifier
    for entry in entries:
        identifier = entry.get('id') if identified_by == 'auto' else entry.render(identified_by)
        if not identifier:
            log.debug('No identifier found for', entry['title'])
            continue
        grouped_entries[identifier.lower()].append(entry)

    return grouped_entries


def is_better_quality_proper(entry, existing):
    if entry['quality'] > existing.quality:
        return True
    if entry['quality'] >= existing.quality and entry.get('proper_count', 0) > existing.proper_count:
        return True
    return False


class LazyUpgrade(object):
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'identified_by': {'type': 'string'},
                    'tracking': {'type': 'boolean'},
                    'target': {'type': 'string', 'format': 'quality_requirements'},
                    'on_lower': {'type': 'string', 'enum': ['accept', 'reject', 'fail', 'skip']},
                    'timeframe': {'type': 'string', 'format': 'interval'},
                    'propers': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if not config or isinstance(config, bool):
            config = {}
        config.setdefault('identified_by', 'auto')
        config.setdefault('tracking', True)
        config.setdefault('on_lower', 'skip')
        config.setdefault('target', None)
        config.setdefault('timeframe', None)
        config.setdefault('propers', True)
        return config

    def filter_entries(self, entries, existing, target):

        # Filter out entries within target
        if target:
            target_requirement = qualities.Requirements(target)
            entries = [e for e in entries if target_requirement.allows(e['quality'])]

        # Filter out entries of lower quality or lower proper count
        entries = [e for e in entries if is_better_quality_proper(e, existing)]

        return entries

    def on_task_filter(self, task, config):
        if not config:
            return

        config = self.prepare_config(config)

        grouped_entries = group_entries(task.entries, config['identified_by'])

        with Session() as session:
            # Prefetch Data
            existing_ids = session.query(EntryUpgrade).filter(EntryUpgrade.id.in_(grouped_entries.keys())).all()
            existing_ids = {e.id: e for e in existing_ids}

            for identifier, entries in grouped_entries.items():
                if not entries:
                    continue

                existing = existing_ids.get(identifier)
                if not existing:
                    # No existing, skip
                    continue

                # Check if passed allowed timeframe
                if config['timeframe']:
                    expires = existing.first_seen + parse_timedelta(config['timeframe'])
                    if expires <= datetime.now():
                        # Timeframe reached, skip
                        continue

                # Check target already met
                if config['target']:
                    target_quality = qualities.Quality(config['target'])
                    target_requirement = qualities.Requirements(config['target'])
                    if existing.quality > target_quality or target_requirement.allows(existing.quality):
                        continue

                # Filter our lower quality and propers
                upgradeable = self.filter_entries(entries, existing, config['target'])

                # Skip if we have no entries after filtering
                if not upgradeable:
                    continue

                # Sort entities in order of quality and best proper
                upgradeable.sort(key=lambda e: (e['quality'], e.get('proper_count', 0)), reverse=True)

                # First entry will be the best quality
                best = upgradeable.pop(0)
                best.accept('upgraded quality')

                # Action lower qualities
                if config['on_lower'] != 'skip':
                    for entry in entries:
                        if entry == best:
                            continue

                        action = entry_actions[config['on_lower']]
                        if entry['quality'] > existing.quality:
                            msg = 'on_lower %s because already at target quality' % config['on_lower']
                            action(entry, msg)
                        elif entry['quality'] < existing.quality:
                            msg = 'on_lower %s because lower then existing quality' % config['on_lower']
                            action(entry, msg)
                        elif entries[0].accepted and entries[0]['quality'] > entry['quality']:
                            msg = 'on_lower %s because lower quality compared to entries' % config['on_lower']
                            action(entry, msg)

    def on_task_learn(self, task, config):
        config = self.prepare_config(config)
        if not config['tracking']:
            return

        grouped_entries = group_entries(task.accepted, config['identified_by'])

        with Session() as session:
            # Prefetch Data
            existing_ids = session.query(EntryUpgrade).filter(EntryUpgrade.id.in_(grouped_entries.keys())).all()
            existing_ids = {e.id: e for e in existing_ids}

            for identifier, entries in grouped_entries.items():
                if not entries:
                    continue

                # Sort entities in order of quality
                entries.sort(key=lambda e: e['quality'], reverse=True)
                # First entry will be the best quality
                best_entry = entries[0]

                existing = existing_ids.get(identifier)

                if not existing:
                    existing = EntryUpgrade()
                    existing.id = identifier
                    session.add(existing)
                elif existing.quality > best_entry['quality']:
                    continue

                existing.quality = best_entry['quality']
                existing.title = best_entry['title']
                existing.proper_count = best_entry.get('proper_count', 0)
                existing.updated = datetime.now()

                log.debug('Tracking upgrade on identifier `%s` current quality `%s`', identifier, best_entry['quality'])


@event('plugin.register')
def register_plugin():
    plugin.register(LazyUpgrade, 'upgrade', builtin=True, api_ver=2)
