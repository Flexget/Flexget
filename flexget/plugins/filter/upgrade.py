from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Unicode

from flexget import db_schema, plugin
from flexget.db_schema import Session
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import qualities
from flexget.utils.database import quality_property
from flexget.utils.tools import group_entries, parse_timedelta

logger = logger.bind(name='upgrade')

Base = db_schema.versioned_base('upgrade', 0)

entry_actions = {'accept': Entry.accept, 'reject': Entry.reject, 'fail': Entry.fail}


class EntryUpgrade(Base):
    __tablename__ = 'upgrade'

    id = Column(Unicode, primary_key=True, index=True)
    title = Column(Unicode)
    _quality = Column('quality', String)
    quality = quality_property('_quality')
    proper_count = Column(Integer, default=0)
    first_seen = Column(DateTime, default=datetime.now)
    updated = Column(DateTime, index=True, default=datetime.now)

    def __str__(self):
        return '<Upgrade(id=%s,added=%s,quality=%s)>' % (self.id, self.added, self.quality)


class FilterUpgrade:
    schema = {
        'type': 'object',
        'properties': {
            'identified_by': {'type': 'string'},
            'tracking': {'type': 'boolean'},
            'target': {'type': 'string', 'format': 'quality_requirements'},
            'on_lower': {'type': 'string', 'enum': ['accept', 'reject', 'do_nothing']},
            'timeframe': {'type': 'string', 'format': 'interval'},
            'propers': {'type': 'boolean'},
        },
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        if not config or config is False:
            return

        if config is True:
            config = {}

        config.setdefault('identified_by', 'auto')
        config.setdefault('tracking', True)
        config.setdefault('on_lower', 'do_nothing')
        config.setdefault('target', None)
        config.setdefault('timeframe', None)
        config.setdefault('propers', True)
        return config

    def filter_entries(self, entries, existing, target, action_on_lower):

        target_requirement = qualities.Requirements(target) if target else None
        filtered = []

        for entry in entries:
            # Filter out entries within target
            if target:
                if not target_requirement.allows(entry['quality']):
                    logger.debug(
                        'Skipping {} as does not meet upgrade quality requirements', entry['title']
                    )
                    if action_on_lower:
                        action_on_lower(entry, 'does not meet upgrade quality requirements')
                    continue

            if entry['quality'] < existing.quality:
                logger.debug('Skipping {} as lower quality then existing', entry['title'])
                if action_on_lower:
                    action_on_lower(entry, 'lower quality then existing')
                continue

            if (
                entry['quality'] == existing.quality
                and entry.get('proper_count', 0) <= existing.proper_count
            ):
                logger.debug('Skipping {} as same quality but lower proper', entry['title'])
                if action_on_lower:
                    action_on_lower(entry, 'lower proper then existing')
                continue

            filtered.append(entry)

        return filtered

    def on_task_filter(self, task, config):
        config = self.prepare_config(config)

        if not config or not config['target']:
            return

        identified_by = (
            '{{ media_id }}' if config['identified_by'] == 'auto' else config['identified_by']
        )

        grouped_entries = group_entries(task.accepted + task.undecided, identified_by)
        if not grouped_entries:
            return

        with Session() as session:
            # Prefetch Data
            existing_ids = (
                session.query(EntryUpgrade)
                .filter(EntryUpgrade.id.in_(grouped_entries.keys()))
                .all()
            )
            existing_ids = {e.id: e for e in existing_ids}

            for identifier, entries in grouped_entries.items():
                if not entries:
                    continue

                existing = existing_ids.get(identifier)
                if not existing:
                    # No existing, do_nothing
                    continue

                logger.debug(
                    'Looking for upgrades for identifier {} (within {} entries)',
                    identifier,
                    len(entries),
                )

                # Check if passed allowed timeframe
                if config['timeframe']:
                    expires = existing.first_seen + parse_timedelta(config['timeframe'])
                    if expires <= datetime.now():
                        # Timeframe reached, allow
                        logger.debug(
                            'Skipping upgrade with identifier {} as timeframe reached', identifier
                        )
                        continue

                # Filter out lower quality and propers
                action_on_lower = (
                    entry_actions[config['on_lower']]
                    if config['on_lower'] != 'do_nothing'
                    else None
                )
                upgradeable = self.filter_entries(
                    entries, existing, config['target'], action_on_lower
                )

                # Skip if we have no entries after filtering
                if not upgradeable:
                    continue

                # Sort entities in order of quality and best proper
                upgradeable.sort(
                    key=lambda e: (e['quality'], e.get('proper_count', 0)), reverse=True
                )

                # First entry will be the best quality
                best = upgradeable.pop(0)
                best.accept('upgraded quality')
                logger.debug(
                    'Found {} as upgraded quality for identifier {}', best['title'], identifier
                )

                # Process rest
                for entry in upgradeable:
                    logger.debug(
                        'Skipping {} as lower quality then best {}', entry['title'], best['title']
                    )
                    if action_on_lower:
                        action_on_lower(entry, 'lower quality then best match')

    def on_task_learn(self, task, config):
        config = self.prepare_config(config)
        if not config or not config['tracking']:
            return

        identified_by = (
            '{{ media_id }}' if config['identified_by'] == 'auto' else config['identified_by']
        )

        grouped_entries = group_entries(task.accepted, identified_by)
        if not grouped_entries:
            return

        with Session() as session:
            # Prefetch Data
            existing_ids = (
                session.query(EntryUpgrade)
                .filter(EntryUpgrade.id.in_(grouped_entries.keys()))
                .all()
            )
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

                logger.debug(
                    'Tracking upgrade on identifier `{}` current quality `{}`',
                    identifier,
                    best_entry['quality'],
                )


@event('plugin.register')
def register_plugin():
    plugin.register(FilterUpgrade, 'upgrade', api_ver=2)
