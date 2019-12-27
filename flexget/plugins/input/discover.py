import datetime
import itertools
import random

from loguru import logger
from sqlalchemy import Column, DateTime, Index, Integer, Unicode

from flexget import db_schema, options, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import aggregate_inputs, multiply_timedelta, parse_timedelta

logger = logger.bind(name='discover')
Base = db_schema.versioned_base('discover', 0)


class DiscoverEntry(Base):
    __tablename__ = 'discover_entry'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    task = Column(Unicode, index=True)
    last_execution = Column(DateTime)

    def __init__(self, title, task):
        self.title = title
        self.task = task
        self.last_execution = None

    def __str__(self):
        return '<DiscoverEntry(title=%s,task=%s,added=%s)>' % (
            self.title,
            self.task,
            self.last_execution,
        )


Index('ix_discover_entry_title_task', DiscoverEntry.title, DiscoverEntry.task)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    value = datetime.datetime.now() - parse_timedelta('7 days')
    for discover_entry in (
        session.query(DiscoverEntry).filter(DiscoverEntry.last_execution <= value).all()
    ):
        logger.debug('deleting {}', discover_entry)
        session.delete(discover_entry)


class Discover:
    """
    Discover content based on other inputs material.

    Example::

      discover:
        what:
          - next_series_episodes: yes
        from:
          - piratebay
        interval: [1 hours|days|weeks]
        release_estimations: [strict|loose|ignore]
    """

    schema = {
        'type': 'object',
        'properties': {
            'what': {
                'type': 'array',
                'items': {
                    'allOf': [
                        {'$ref': '/schema/plugins?phase=input'},
                        {'maxProperties': 1, 'minProperties': 1},
                    ]
                },
            },
            'from': {
                'type': 'array',
                'items': {
                    'allOf': [
                        {'$ref': '/schema/plugins?interface=search'},
                        {'maxProperties': 1, 'minProperties': 1},
                    ]
                },
            },
            'interval': {'type': 'string', 'format': 'interval', 'default': '5 hours'},
            'release_estimations': {
                'oneOf': [
                    {'type': 'string', 'default': 'strict', 'enum': ['loose', 'strict', 'ignore']},
                    {
                        'type': 'object',
                        'properties': {'optimistic': {'type': 'string', 'format': 'interval'}},
                        'required': ['optimistic'],
                    },
                ]
            },
            'limit': {'type': 'integer', 'minimum': 1},
        },
        'required': ['what', 'from'],
        'additionalProperties': False,
    }

    def execute_searches(self, config, entries, task):
        """
        :param config: Discover plugin config
        :param entries: List of pseudo entries to search
        :param task: Task being run
        :return: List of entries found from search engines listed under `from` configuration
        """

        result = []
        for index, entry in enumerate(entries):
            entry_results = []
            for item in config['from']:
                if isinstance(item, dict):
                    plugin_name, plugin_config = list(item.items())[0]
                else:
                    plugin_name, plugin_config = item, None
                search = plugin.get(plugin_name, self)
                if not callable(getattr(search, 'search')):
                    logger.critical(
                        'Search plugin {} does not implement search method', plugin_name
                    )
                    continue
                logger.verbose(
                    'Searching for `{}` with plugin `{}` ({} of {})',
                    entry['title'],
                    plugin_name,
                    index + 1,
                    len(entries),
                )
                try:
                    search_results = search.search(task=task, entry=entry, config=plugin_config)
                    if not search_results:
                        logger.debug('No results from {}', plugin_name)
                        continue
                    if config.get('limit'):
                        search_results = itertools.islice(search_results, config['limit'])
                    # 'search_results' can be any iterable, make sure it's a list.
                    search_results = list(search_results)
                    logger.debug('Discovered {} entries from {}', len(search_results), plugin_name)
                    for e in search_results:
                        e['discovered_from'] = entry['title']
                        e['discovered_with'] = plugin_name
                        e.on_complete(
                            self.entry_complete, query=entry, search_results=search_results
                        )

                    entry_results.extend(search_results)

                except plugin.PluginWarning as e:
                    logger.verbose('No results from {}: {}', plugin_name, e)
                except plugin.PluginError as e:
                    logger.error('Error searching with {}: {}', plugin_name, e)
            if not entry_results:
                logger.verbose('No search results for `{}`', entry['title'])
                entry.complete()
                continue
            result.extend(entry_results)

        return result

    def entry_complete(self, entry, query=None, search_results=None, **kwargs):
        """Callback for Entry"""
        if entry.accepted:
            # One of the search results was accepted, transfer the acceptance back to the query entry which generated it
            query.accept()
        # Remove this entry from the list of search results yet to complete
        search_results.remove(entry)
        # When all the search results generated by a query entry are complete, complete the query which generated them
        if not search_results:
            query.complete()

    def estimated(self, entries, estimation_mode):
        """
        :param dict estimation_mode: mode -> loose, strict, ignore
        :return: Entries that we have estimated to be available
        """
        estimator = plugin.get('estimate_release', self)
        result = []
        for entry in entries:
            est_date = estimator.estimate(entry)
            if est_date is None:
                logger.debug('No release date could be determined for {}', entry['title'])
                if estimation_mode['mode'] == 'strict':
                    entry.reject('has no release date')
                    entry.complete()
                else:
                    result.append(entry)
                continue
            if isinstance(est_date, datetime.date):
                # If we just got a date, add a time so we can compare it to now()
                est_date = datetime.datetime.combine(est_date, datetime.time())
            if datetime.datetime.now() >= est_date:
                logger.debug('{} has been released at {}', entry['title'], est_date)
                result.append(entry)
            elif datetime.datetime.now() >= est_date - parse_timedelta(
                estimation_mode['optimistic']
            ):
                logger.debug(
                    '{} will be released at {}. Ignoring release estimation because estimated release date is in less than {}',
                    entry['title'],
                    est_date,
                    estimation_mode['optimistic'],
                )
                result.append(entry)
            else:
                entry.reject('has not been released')
                entry.complete()
                logger.verbose(
                    "{} hasn't been released yet (Expected: {})", entry['title'], est_date
                )
        return result

    def interval_expired(self, config, task, entries):
        """
        Maintain some limit levels so that we don't hammer search
        sites with unreasonable amount of queries.

        :return: Entries that are up for ``config['interval']``
        """
        config.setdefault('interval', '5 hour')
        interval = parse_timedelta(config['interval'])
        if task.options.discover_now:
            logger.info('Ignoring interval because of --discover-now')
        result = []
        interval_count = 0
        with Session() as session:
            for entry in entries:
                discover_entry = (
                    session.query(DiscoverEntry)
                    .filter(DiscoverEntry.title == entry['title'])
                    .filter(DiscoverEntry.task == task.name)
                    .first()
                )

                if not discover_entry:
                    logger.debug('{} -> No previous run recorded', entry['title'])
                    discover_entry = DiscoverEntry(entry['title'], task.name)
                    session.add(discover_entry)
                if (
                    not task.is_rerun and task.options.discover_now
                ) or not discover_entry.last_execution:
                    # First time we execute (and on --discover-now) we randomize time to avoid clumping
                    delta = multiply_timedelta(interval, random.random())
                    discover_entry.last_execution = datetime.datetime.now() - delta
                else:
                    next_time = discover_entry.last_execution + interval
                    logger.debug(
                        'last_time: {!r}, interval: {}, next_time: {!r}, ',
                        discover_entry.last_execution,
                        config['interval'],
                        next_time,
                    )
                    if datetime.datetime.now() < next_time:
                        logger.debug('interval not met')
                        interval_count += 1
                        entry.reject('discover interval not met')
                        entry.complete()
                        continue
                    discover_entry.last_execution = datetime.datetime.now()
                logger.trace('interval passed for {}', entry['title'])
                result.append(entry)
        if interval_count and not task.is_rerun:
            logger.verbose(
                'Discover interval of {} not met for {} entries. Use --discover-now to override.',
                config['interval'],
                interval_count,
            )
        return result

    def on_task_input(self, task, config):
        config.setdefault('release_estimations', {})
        if not isinstance(config['release_estimations'], dict):
            config['release_estimations'] = {'mode': config['release_estimations']}

        config['release_estimations'].setdefault('mode', 'strict')
        config['release_estimations'].setdefault('optimistic', '0 days')

        task.no_entries_ok = True
        entries = aggregate_inputs(task, config['what'])
        logger.verbose('Discovering {} titles ...', len(entries))
        if len(entries) > 500:
            logger.critical(
                'Looks like your inputs in discover configuration produced '
                'over 500 entries, please reduce the amount!'
            )
        # TODO: the entries that are estimated should be given priority over expiration
        entries = self.interval_expired(config, task, entries)
        estimation_mode = config['release_estimations']
        if estimation_mode['mode'] != 'ignore':
            entries = self.estimated(entries, estimation_mode)
        return self.execute_searches(config, entries, task)


@event('plugin.register')
def register_plugin():
    plugin.register(Discover, 'discover', api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--discover-now',
        action='store_true',
        dest='discover_now',
        default=False,
        help='Immediately try to discover everything',
    )
