from __future__ import unicode_literals, division, absolute_import
import logging

from sqlalchemy import Column, Integer, DateTime, Unicode, and_, Index
from flexget.event import event

from flexget.utils.cached_input import cached
from flexget.utils.search import StringComparator, MovieComparator, AnyComparator, clean_title
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError, \
    get_plugins_by_group, get_plugins_by_phase, PluginWarning, register_parser_option
import datetime
from flexget import schema
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('discover')
Base = schema.versioned_base('discover', 0)


class DiscoverEntry(Base):
    __tablename__ = 'discover_entry'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    task = Column(Unicode, index=True)
    last_execution = Column(DateTime)

    def __init__(self, title, task):
        self.title = title
        self.task = task
        self.last_execution = datetime.datetime.now()

    def __str__(self):
        return '<DiscoverEntry(title=%s,task=%s,added=%s)>' % (self.title, self.task, self.last_execution)

Index('ix_discover_entry_title_task', DiscoverEntry.title, DiscoverEntry.task)


@event('manager.db_cleanup')
def db_cleanup(session):
    value = datetime.datetime.now() - parse_timedelta('7 days')
    for de in session.query(DiscoverEntry).filter(DiscoverEntry.last_execution <= value).all():
        log.debug('deleting %s' % de)
        session.delete(de)


class Discover(object):
    """
    Discover content based on other inputs material.

    Example::

      discover:
        what:
          - emit_series: yes
        from:
          - piratebay
        type: [any|normal|exact|movies]
        interval: [1 hours|days|weeks]
        ignore_estimations: [yes|no]
    """

    def validator(self):
        from flexget import validator
        discover = validator.factory('dict')

        inputs = discover.accept('list', key='what', required=True).accept('dict')
        for plugin in get_plugins_by_phase('input'):
            if hasattr(plugin.instance, 'validator'):
                inputs.accept(plugin.instance.validator, key=plugin.name)

        searches = discover.accept('list', key='from', required=True)
        no_config = searches.accept('choice')
        for plugin in get_plugins_by_group('search'):
            if hasattr(plugin.instance, 'validator'):
                searches.accept('dict').accept(plugin.instance.validator, key=plugin.name)
            else:
                no_config.accept(plugin.name)

        discover.accept('integer', key='limit')
        discover.accept('interval', key='interval')
        discover.accept('boolean', key='ignore_estimations')
        discover.accept('choice', key='type').accept_choices(['any', 'normal', 'exact', 'movies'])
        return discover

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
            for input_name, input_config in item.iteritems():
                input = get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise PluginError('Plugin %s does not support API v2' % input_name)
                method = input.phase_handlers['input']
                try:
                    result = method(task, input_config)
                except PluginError as e:
                    log.warning('Error during input plugin %s: %s' % (input_name, e))
                    continue
                if not result:
                    log.warning('Input %s did not return anything' % input_name)
                    continue

                for entry in result:
                    urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                    if any(url in entry_urls for url in urls):
                        log.debug('URL for `%s` already in entry list, skipping.' % entry['title'])
                        continue

                    if entry['title'] in entry_titles:
                        log.verbose('Ignored duplicate title `%s`' % entry['title'])    # TODO: should combine?
                    else:
                        entries.append(entry)
                        entry_titles.add(entry['title'])
                        entry_urls.update(urls)
        return entries

    def execute_searches(self, config, entries):
        """
        :param config: Discover plugin config
        :param entries: List of pseudo entries to search
        :return: List of entries found from search engines listed under `from` configuration
        """

        result = []
        if config.get('type', 'normal') == 'normal':
            comparator = StringComparator(cutoff=0.7, cleaner=clean_title)
        elif config['type'] == 'exact':
            comparator = StringComparator(cutoff=0.9)
        elif config['type'] == 'any':
            comparator = AnyComparator()
        else:
            comparator = MovieComparator()
        for item in config['from']:
            if isinstance(item, dict):
                plugin_name, plugin_config = item.items()[0]
            else:
                plugin_name, plugin_config = item, None
            search = get_plugin_by_name(plugin_name).instance
            if not callable(getattr(search, 'search')):
                log.critical('Search plugin %s does not implement search method' % plugin_name)
            for entry in entries:
                try:
                    search_results = search.search(entry, comparator, plugin_config)
                    log.debug('Discovered %s entries from %s' % (len(search_results), plugin_name))
                    result.extend(search_results[:config.get('limit')])
                except (PluginError, PluginWarning):
                    log.debug('No results from %s' % plugin_name)
        return sorted(result, reverse=True, key=lambda x: x.get('search_sort'))

    def estimated(self, entries):
        """
        :return: Entries that we have estimated to be available
        """
        estimator = get_plugin_by_name('estimate_release').instance
        result = []
        for entry in entries:
            est_date = estimator.estimate(entry)
            if est_date is None:
                log.debug('No release date could be determined for %s' % entry['title'])
                result.append(entry)
            elif datetime.datetime.now().date() >= est_date:
                log.info('%s has been released at %s' % (entry['title'], est_date))
                result.append(entry)
            else:
                log.info("%s hasn't been released yet (Expected:%s)" % (entry['title'], est_date))
        return result

    def interval_expired(self, config, task, entries):
        """
        Maintain some limit levels so that we don't hammer search
        sites with unreasonable amount of queries.

        :return: Entries that are up for ``config['interval']``
        """
        config.setdefault('interval', '5 hour')
        interval = parse_timedelta(config['interval'])
        result = []
        for entry in entries:
            de = task.session.query(DiscoverEntry).filter(and_(DiscoverEntry.title == entry['title'],
                                                               DiscoverEntry.task == task.name)).first()
            if not de:
                last_time = None
            else:
                last_time = de.last_execution

            if not last_time:
                log.info('%s -> No previous run recorded, running now' % entry['title'])
            elif task.manager.options.discover_now:
                log.info('Ignoring interval because of --discover-now')
            else:
                log.debug('last_time: %r' % last_time)
                log.debug('interval: %s' % config['interval'])
                next_time = last_time + interval
                log.debug('next_time: %r' % next_time)
                if datetime.datetime.now() < next_time:
                    log.debug('interval not met')
                    log.verbose('Discover interval %s not met for %s. Use --discover-now to override.' %
                                (config['interval'], entry['title']))
                    continue
            log.debug('interval passed')
            if not de:
                de = DiscoverEntry(entry['title'], unicode(task.name))
                task.session.add(de)
            else:
                de.last_execution = datetime.datetime.now()
                task.session.merge(de)
            result.append(entry)
        return result

    @cached('discover')
    def on_task_input(self, task, config):
        task.no_entries_ok = True
        entries = self.execute_inputs(config, task)
        log.verbose('Discovering %i titles ...' % len(entries))
        if len(entries) > 500:
            log.critical('Looks like your inputs in discover configuration produced '
                         'over 500 entries, please reduce the amount!')
        # TODO: the entries that are estimated should be given priority over expiration
        entries = self.interval_expired(config, task, entries)
        if not config.get('ignore_estimations', False):
            entries = self.estimated(entries)
        return self.execute_searches(config, entries)


register_plugin(Discover, 'discover', api_ver=2)
register_parser_option('--discover-now', action='store_true', dest='discover_now', default=False,
                       help='Immediately try to discover everything.')
