from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import datetime
import logging
import random

from sqlalchemy import Column, Integer, DateTime, Unicode, Index

from flexget import options, plugin
from flexget import db_schema
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name, PluginError, PluginWarning
from flexget.utils.tools import parse_timedelta, multiply_timedelta

log = logging.getLogger('discover')
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
        return '<DiscoverEntry(title=%s,task=%s,added=%s)>' % (self.title, self.task, self.last_execution)


Index('ix_discover_entry_title_task', DiscoverEntry.title, DiscoverEntry.task)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    value = datetime.datetime.now() - parse_timedelta('7 days')
    for discover_entry in session.query(DiscoverEntry).filter(DiscoverEntry.last_execution <= value).all():
        log.debug('deleting %s', discover_entry)
        session.delete(discover_entry)


class Discover(object):
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
            'what': {'type': 'array', 'items': {
                'allOf': [{'$ref': '/schema/plugins?phase=input'}, {'maxProperties': 1, 'minProperties': 1}]
            }},
            'from': {'type': 'array', 'items': {
                'allOf': [{'$ref': '/schema/plugins?interface=search'}, {'maxProperties': 1, 'minProperties': 1}]
            }},
            'interval': {'type': 'string', 'format': 'interval', 'default': '5 hours'},
            'release_estimations': {
                'oneOf': [
                    {'type': 'string', 'default': 'strict', 'enum': ['loose', 'strict', 'ignore']},
                    {
                        'type': 'object',
                        'properties': {
                            'optimistic': {'type': 'string', 'format': 'interval'}
                        },
                        'required': ['optimistic']
                    }
                ]
            },
            'limit': {'type': 'integer', 'minimum': 1}
        },
        'required': ['what', 'from'],
        'additionalProperties': False
    }

    def execute_inputs(self, config, task):
        """
        :param config: Discover config
        :param task: Current task
        :return: List of pseudo entries created by inputs under `what` configuration
        """
        entries = []
        entry_titles = set()
        entry_urls = set()
        # run inputs
        for item in config['what']:
            for input_name, input_config in item.items():
                input = get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise PluginError('Plugin %s does not support API v2' % input_name)
                method = input.phase_handlers['input']
                try:
                    result = method(task, input_config)
                except PluginError as e:
                    log.warning('Error during input plugin %s: %s', input_name, e)
                    continue
                if not result:
                    log.warning('Input %s did not return anything', input_name)
                    continue

                for entry in result:
                    urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                    if any(url in entry_urls for url in urls):
                        log.debug('URL for `%s` already in entry list, skipping.', entry['title'])
                        continue

                    if entry['title'] in entry_titles:
                        log.verbose('Ignored duplicate title `%s`', entry['title'])  # TODO: should combine?
                        continue

                    entries.append(entry)
                    entry_titles.add(entry['title'])
                    entry_urls.update(urls)
        return entries

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
                search = get_plugin_by_name(plugin_name).instance
                if not callable(getattr(search, 'search')):
                    log.critical('Search plugin %s does not implement search method', plugin_name)
                    continue
                log.verbose('Searching for `%s` with plugin `%s` (%i of %i)', entry['title'], plugin_name, index + 1,
                            len(entries))
                try:
                    search_results = search.search(task=task, entry=entry, config=plugin_config)
                    if not search_results:
                        log.debug('No results from %s', plugin_name)
                        continue
                    log.debug('Discovered %s entries from %s', len(search_results), plugin_name)
                    if config.get('limit'):
                        search_results = sorted(search_results, reverse=True,
                                                key=lambda x: x.get('search_sort', ''))[:config['limit']]
                    for e in search_results:
                        e['discovered_from'] = entry['title']
                        e['discovered_with'] = plugin_name
                        e.on_complete(self.entry_complete, query=entry, search_results=search_results)

                    entry_results.extend(search_results)

                except PluginWarning as e:
                    log.verbose('No results from %s: %s', plugin_name, e)
                except PluginError as e:
                    log.error('Error searching with %s: %s', plugin_name, e)
            if not entry_results:
                log.verbose('No search results for `%s`', entry['title'])
                entry.complete()
                continue
            result.extend(entry_results)

        return sorted(result, reverse=True, key=lambda x: x.get('search_sort', -1))

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
        estimator = get_plugin_by_name('estimate_release').instance
        result = []
        for entry in entries:
            est_date = estimator.estimate(entry)
            if est_date is None:
                log.debug('No release date could be determined for %s', entry['title'])
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
                log.debug('%s has been released at %s', entry['title'], est_date)
                result.append(entry)
            elif datetime.datetime.now() >= est_date - parse_timedelta(estimation_mode['optimistic']):
                log.debug('%s will be released at %s. Ignoring release estimation because estimated release date is '
                          'in less than %s', entry['title'], est_date, estimation_mode['optimistic'])
                result.append(entry)
            else:
                entry.reject('has not been released')
                entry.complete()
                log.verbose("%s hasn't been released yet (Expected: %s)", entry['title'], est_date)
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
            log.info('Ignoring interval because of --discover-now')
        result = []
        interval_count = 0
        with Session() as session:
            for entry in entries:
                discover_entry = session.query(DiscoverEntry). \
                    filter(DiscoverEntry.title == entry['title']). \
                    filter(DiscoverEntry.task == task.name).first()

                if not discover_entry:
                    log.debug('%s -> No previous run recorded', entry['title'])
                    discover_entry = DiscoverEntry(entry['title'], task.name)
                    session.add(discover_entry)
                if (not task.is_rerun and task.options.discover_now) or not discover_entry.last_execution:
                    # First time we execute (and on --discover-now) we randomize time to avoid clumping
                    delta = multiply_timedelta(interval, random.random())
                    discover_entry.last_execution = datetime.datetime.now() - delta
                else:
                    next_time = discover_entry.last_execution + interval
                    log.debug('last_time: %r, interval: %s, next_time: %r, ',
                              discover_entry.last_execution, config['interval'], next_time)
                    if datetime.datetime.now() < next_time:
                        log.debug('interval not met')
                        interval_count += 1
                        entry.reject('discover interval not met')
                        entry.complete()
                        continue
                    discover_entry.last_execution = datetime.datetime.now()
                log.trace('interval passed for %s', entry['title'])
                result.append(entry)
        if interval_count and not task.is_rerun:
            log.verbose('Discover interval of %s not met for %s entries. Use --discover-now to override.',
                        config['interval'], interval_count)
        return result

    def on_task_input(self, task, config):
        config.setdefault('release_estimations', {})
        if not isinstance(config['release_estimations'], dict):
            config['release_estimations'] = {'mode': config['release_estimations']}

        config['release_estimations'].setdefault('mode', 'strict')
        config['release_estimations'].setdefault('optimistic', '0 days')

        task.no_entries_ok = True
        entries = self.execute_inputs(config, task)
        log.verbose('Discovering %i titles ...', len(entries))
        if len(entries) > 500:
            log.critical('Looks like your inputs in discover configuration produced '
                         'over 500 entries, please reduce the amount!')
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
    options.get_parser('execute').add_argument('--discover-now', action='store_true', dest='discover_now',
                                               default=False, help='Immediately try to discover everything')
